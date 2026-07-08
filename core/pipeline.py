import asyncio
import json
import os
import structlog
from typing import Dict, List, TypedDict, Union, Optional

try:
    from langgraph.graph import StateGraph, END
    from pydantic import BaseModel
except ImportError:
    StateGraph = None
    END = None
    BaseModel = None

logger = structlog.get_logger("SATURDAY.Pipeline")
class PipelineState(TypedDict):
    user_input: str
    source: str
    reply: str
    tasks: List[Dict]
    lang_hint: Optional[str]
    metadata: Dict
    status: str
class SATURDAYPipeline:
    def __init__(self, llm_engine, speech_manager, event_bus, task_manager, learning_manager=None):
        self.llm = llm_engine
        self.speech = speech_manager
        self.event_bus = event_bus
        self.tasks = task_manager
        self.learning = learning_manager
        self.config = {}
        config_path = "core/config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.config = json.load(f)
            except: pass
        self.use_autogen = self.config.get("ai", {}).get("use_autogen", False)
        self.graph = self._build_graph()
        logger.info("SATURDAY LangGraph pipeline initialized.", use_autogen=self.use_autogen)
    def _build_graph(self):
        workflow = StateGraph(PipelineState)
        workflow.add_node("input_planner", self._node_planner)
        workflow.add_node("response_generator", self._node_response_generator)
        workflow.add_node("executor", self._node_executor)
        workflow.set_entry_point("input_planner")
        workflow.add_edge("input_planner", "response_generator")
        workflow.add_edge("response_generator", "executor")
        workflow.add_edge("executor", END)
        return workflow.compile()
    async def _node_planner(self, state: PipelineState) -> PipelineState:
        if self.use_autogen and state.get("source") != "voice":
            logger.info("Using AutoGen team for planning.")
            plan_data = await self._run_autogen_team(state["user_input"])
            state["metadata"]["autogen_plan"] = plan_data
            if "TASK:" in plan_data:
                self.event_bus.publish("task_request", {"text": state["user_input"]})
            if "SEARCH:" in plan_data:
                 self.event_bus.publish("search_request", {"query": state["user_input"]})
            return state
        user_text = state["user_input"].lower()
        if any(kw in user_text for kw in ["run ", "execute ", "start ", "schedule ", "do "]):
            self.event_bus.publish("task_request", {"text": state["user_input"], "source": state["source"]})
        if any(kw in user_text for kw in ["search ", "look up ", "google ", "find info"]):
            query = state["user_input"].replace("search", "").replace("look up", "").strip() or state["user_input"]
            self.event_bus.publish("search_request", {"query": query})
        return state
    async def _run_autogen_team(self, user_input: str) -> str:
        if not self.llm:
            return ""
        prompt = (
            "You are the SATURDAY planner. "
            "Return at most three short lines. "
            "Use 'TASK:' for concrete OS or device actions. "
            "Use 'SEARCH:' when external information is required. "
            "Use 'REPLY:' for the conversational angle. "
            "Do not invent execution results.\n\n"
            f"User input: {user_input}"
        )
        plan_chunks = []
        try:
            async for chunk in self.llm.chat_stream(prompt):
                plan_chunks.append(chunk)
        except Exception as e:
            logger.warning("Planner fallback failed.", error=str(e))
            return ""
        return "".join(plan_chunks).strip()
    async def _node_response_generator(self, state: PipelineState) -> PipelineState:
        if not self.llm:
            state["reply"] = "The language model is unavailable right now."
            return state
        prompt = self._build_prompt(state)
        chunks = []
        async for chunk in self.llm.chat_stream(prompt):
            chunks.append(chunk)
        state["reply"] = "".join(chunks).strip()
        return state
    async def _node_executor(self, state: PipelineState) -> PipelineState:
        reply = state["reply"]
        if not reply:
            return state
        self.event_bus.publish("voice_response", reply)
        if self.learning:
            self.learning.record("exchange", {"user": state["user_input"], "reply": reply})
        return state
    def _build_prompt(self, state: PipelineState) -> str:
        autogen_info = f"\nStrategist plan: {state['metadata'].get('autogen_plan', '')}" if self.use_autogen else ""
        long_term = self.learning.get_summaries_text() if self.learning else ""
        return (
            "You are SATURDAY, a warm, concise, human-like AI operating system. "
            f"{autogen_info}\n\n"
            f"User input: {state['user_input']}\n"
            f"Contextual knowledge: {long_term}\n\n"
            "Response:"
        )
    async def run(self, user_input: str, source: str = "text", lang_hint: str = None) -> Dict:
        initial_state = {
            "user_input": user_input,
            "source": source,
            "reply": "",
            "tasks": [],
            "lang_hint": lang_hint,
            "metadata": {},
            "status": "started"
        }
        try:
            result = await self.graph.ainvoke(initial_state)
            return result
        except Exception as e:
            logger.warning("Pipeline execution failed.", error=str(e))
            return {"error": str(e), "reply": "I encountered an error while processing that."}
