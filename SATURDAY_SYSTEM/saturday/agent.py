"""SATURDAY Agent — goal-driven autonomy: think → act → observe.

Two ways to use it:
1. COMMANDED  : `do <goal>` / `research <topic>` — SATURDAY decomposes the
   goal into a plan and executes it step by step by itself.
2. SUPERVISED : goals with no template pause and ask the user for the next
   move, then execute it, observe the result, and ask again — the user
   commands, SATURDAY does the hands work.

Thinking model (transparent, logged, no black box):
- TemplateBrain turns a goal into an explicit plan (list of action dicts).
- AgentRunner executes one step at a time, feeds each result back as the
  next observation, records a full transcript, and stops on done/failure/
  step budget. Findings are stored via the injected store_fn (PMV vault).
- A local LLM/vision model can later replace TemplateBrain by subclassing
  Brain and implementing decide(task, observation).

Every action returns {"success": bool, ...}; the runner never raises.
"""

import logging
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Agent")

PromptFn = Callable[[str, Dict[str, Any]], str]
StoreFn = Callable[[str, List[str]], str]


class AgentTask:
    def __init__(self, goal: str, plan: List[Dict[str, Any]]):
        self.id = str(uuid.uuid4())[:8]
        self.goal = goal
        self.plan = plan
        self.step_idx = 0
        self.status = "running"  # running | done | failed | stopped
        self.transcript: List[Dict[str, Any]] = []
        self.findings: List[str] = []
        self.started_at = time.time()

    def summary(self) -> str:
        steps = len(self.transcript)
        if self.status == "done":
            head = f"✅ Task {self.id} done in {steps} steps: {self.goal}"
        elif self.status == "failed":
            head = f"❌ Task {self.id} failed at step {self.step_idx + 1}: {self.goal}"
        else:
            head = f"⏹️ Task {self.id} {self.status}: {self.goal}"
        notes = self.findings[:3]
        extra = ("\n   Findings: " + " | ".join(n[:100] for n in notes)) if notes else ""
        return head + extra


class Brain:
    """Decide the next action. Override for smarter brains."""

    def decide(self, task: AgentTask, observation: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class TemplateBrain(Brain):
    """Follows the task plan step by step; asks user when plan runs dry."""

    def decide(self, task: AgentTask, observation: Dict[str, Any]) -> Dict[str, Any]:
        if task.step_idx < len(task.plan):
            return task.plan[task.step_idx]
        return {"action": "ask", "prompt": "Plan finished. What next? (type 'done' to finish)"}


def research_plan(topic: str) -> List[Dict[str, Any]]:
    query = "+".join(topic.split())
    return [
        {"action": "open_url", "args": {"url": f"https://html.duckduckgo.com/html/?q={query}"},
         "why": f"search the web for '{topic}'"},
        {"action": "screenshot", "args": {}, "why": "capture results"},
        {"action": "read", "args": {}, "why": "read result text off the screen"},
        {"action": "store", "args": {"tags": ["research"]},
         "why": "save findings to the encrypted vault"},
        {"action": "done", "args": {}},
    ]


def supervised_plan(goal: str) -> List[Dict[str, Any]]:
    return [{"action": "ask",
             "prompt": f"Goal: {goal}. Tell me the first move (a screen command like 'open gmail', or 'done')."}]


class AgentRunner:
    def __init__(self, operator, brain: Optional[Brain] = None,
                 store_fn: Optional[StoreFn] = None,
                 prompter: Optional[PromptFn] = None,
                 max_steps: int = 15, confirm: bool = True):
        self.operator = operator
        self.brain = brain or TemplateBrain()
        self.store_fn = store_fn
        self.prompter = prompter
        self.max_steps = max_steps
        self.confirm = confirm
        self.history: List[AgentTask] = []

    # -- main loop -----------------------------------------------------
    def run(self, task: AgentTask) -> AgentTask:
        logger.info(f"Agent starting task {task.id}: {task.goal}")
        observation: Dict[str, Any] = {"success": True, "note": "task started"}
        steps = 0
        while task.status == "running" and steps < self.max_steps:
            steps += 1
            try:
                step = self.brain.decide(task, observation)
            except Exception as e:
                return self._fail(task, f"brain error: {e}")
            result = self._execute(task, step, observation)
            task.transcript.append({"step": step, "result": self._short(result)})
            observation = result
            if result.get("task_done"):
                task.status = "done"
            elif result.get("task_failed"):
                task.status = "failed"
            elif not result.get("stay"):
                task.step_idx += 1
            # "stay" = the step rewrote the plan under us (ask queued a
            # sub-step and already pointed step_idx at it).
        if task.status == "running":
            task.status = "stopped" if steps >= self.max_steps else task.status
            if steps >= self.max_steps:
                task.transcript.append({"step": {"action": "limit"}, "result": "step budget exhausted"})
        logger.info(f"Agent task {task.id} finished: {task.status}")
        self.history.append(task)
        self.history = self.history[-50:]  # bounded for long runs
        return task

    # -- step execution --------------------------------------------------
    def _execute(self, task: AgentTask, step: Dict[str, Any], observation: Dict[str, Any]) -> Dict[str, Any]:
        # Local models often echo signatures ("open_url(url)") — normalize.
        action = re.split(r"[\s(]", str(step.get("action", "")).lower())[0]
        args = step.get("args", {}) or {}
        if isinstance(args, str):
            args = {"text": args}
        op = self.operator
        c = self.confirm
        try:
            if action == "open_url":
                return op.open_url(args.get("url", ""), confirm=c)
            if action == "open_app":
                return op.open_app(args.get("app", ""), confirm=c)
            if action == "screenshot":
                return op.screenshot()
            if action == "read":
                res = op.read_screen()
                if res.get("success"):
                    task.findings.append(res.get("text", "")[:2000])
                return res
            if action == "describe":
                # Brain looks at the screen through the vision model.
                seer = getattr(self.brain, "see", None)
                if seer is None:
                    return {"success": False, "task_failed": True,
                            "error": "this brain has no eyes (no vision model)"}
                shot = op.screenshot()
                if not shot.get("success"):
                    return shot
                res = seer(shot["path"])
                if res.get("success"):
                    task.findings.append(res.get("description", "")[:2000])
                return res
            if action == "store":
                if not self.store_fn:
                    return {"success": False, "task_failed": True, "error": "no vault connected"}
                content = "\n".join(task.findings) or str(observation)[:2000]
                entry_id = self.store_fn(f"[{task.goal}]\n{content}", args.get("tags", []))
                task.findings.append(f"vault entry {entry_id}")
                return {"success": True, "entry_id": entry_id}
            if action == "click":
                return op.click(args.get("x"), args.get("y"), confirm=c)
            if action == "click_text":
                return op.click_text(args.get("text", ""), confirm=c)
            if action == "type":
                return op.type_text(args.get("text", ""), confirm=c)
            if action == "press":
                return op.press(args.get("key", ""), confirm=c)
            if action == "hotkey":
                return op.hotkey(args.get("keys", []), confirm=c)
            if action == "scroll":
                return op.scroll(args.get("amount", 0), confirm=c)
            if action == "ask":
                return self._ask(task, step, observation)
            if action == "done":
                return {"success": True, "task_done": True}
            return {"success": False, "task_failed": True, "error": f"unknown action: {action}"}
        except Exception as e:
            logger.warning(f"Agent step failed: {e}")
            return {"success": False, "task_failed": True, "error": str(e)}

    def _ask(self, task: AgentTask, step: Dict[str, Any], observation: Dict[str, Any]) -> Dict[str, Any]:
        if not self.prompter:
            return {"success": False, "task_failed": True,
                    "error": "No user available for decisions (remote mode)."}
        prompt = step.get("prompt", "What next?") + f" [last: {self._short(observation)}]"
        try:
            answer = (self.prompter(prompt, observation) or "").strip()
        except Exception as e:
            return {"success": False, "task_failed": True, "error": f"prompt failed: {e}"}
        if answer.lower() in ("done", "stop", "quit", "exit"):
            return {"success": True, "task_done": True}
        if not answer:
            return {"success": False, "error": "empty answer, asking again"}
        # Treat the answer as inline sub-steps: splice them into the plan
        # at the current position and stay there so they execute next.
        sub = self._parse_command_answer(answer)
        idx = min(task.step_idx + 1, len(task.plan))
        task.plan.insert(idx, sub)
        task.step_idx = idx
        return {"success": True, "stay": True, "note": f"queued: {answer[:80]}"}

    @staticmethod
    def _parse_command_answer(answer: str) -> Dict[str, Any]:
        parts = answer.split(None, 1)
        verb = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""
        if verb == "click":
            xy = rest.split()
            return {"action": "click", "args": {"x": xy[0] if xy else 0, "y": xy[1] if len(xy) > 1 else 0}}
        if verb in ("clicktext", "click_text"):
            return {"action": "click_text", "args": {"text": rest}}
        if verb == "type":
            return {"action": "type", "args": {"text": rest}}
        if verb == "press":
            return {"action": "press", "args": {"key": rest}}
        if verb == "hotkey":
            return {"action": "hotkey", "args": {"keys": rest.split()}}
        if verb == "scroll":
            return {"action": "scroll", "args": {"amount": rest}}
        if verb == "open":
            if " " not in rest and ("." in rest or rest.lower() in ("gmail", "mail")):
                return {"action": "open_url", "args": {"url": rest}}
            return {"action": "open_app", "args": {"app": rest}}
        if verb in ("see", "shot", "screenshot"):
            return {"action": "screenshot", "args": {}}
        if verb == "read":
            return {"action": "read", "args": {}}
        return {"action": "open_app", "args": {"app": answer}}

    def _fail(self, task: AgentTask, reason: str) -> AgentTask:
        task.status = "failed"
        task.transcript.append({"step": {"action": "error"}, "result": reason})
        self.history.append(task)
        return task

    @staticmethod
    def _short(result: Dict[str, Any]) -> str:
        if not isinstance(result, dict):
            return str(result)[:200]
        if result.get("success"):
            keys = [f"{k}={str(v)[:60]}" for k, v in result.items() if k != "success"]
            return "ok: " + ", ".join(keys[:4])
        return "fail: " + str(result.get("error", "?"))[:200]
