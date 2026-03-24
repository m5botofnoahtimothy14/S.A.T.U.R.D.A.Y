"""
HumanInterface
---------------
Natural, conversational layer that:
- Listens for voice/text commands on the event bus.
- Generates human-like replies via the LLMEngine with short-term memory.
- Speaks responses aloud through SpeechManager.
"""
import asyncio
from collections import deque
from typing import Deque, Tuple

import structlog

logger = structlog.get_logger("AEGIS.HumanInterface")


from core.pipeline import AEGISPipeline
import json
import os

class HumanInterface:
    def __init__(self, event_bus, llm_engine, speech_manager, task_manager, learning_manager=None, memory_size: int = 10):
        self.event_bus = event_bus
        self.llm = llm_engine
        self.speech = speech_manager
        self.tasks = task_manager
        self.learning = learning_manager
        self.memory: Deque[Tuple[str, str]] = deque(maxlen=memory_size)
        self.direct_speech = os.getenv("AEGIS_DIRECT_SPEECH", "false").lower() in ("1", "true", "yes", "on")
        self.voice_input_enabled = True
        
        self.config = {}
        config_path = "core/config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config for HumanInterface: {e}")
        
        self.use_langgraph = self.config.get("ai", {}).get("use_langgraph", False)
        
        self.pipeline = AEGISPipeline(
            llm_engine=llm_engine,
            speech_manager=speech_manager,
            event_bus=event_bus,
            task_manager=task_manager,
            learning_manager=learning_manager
        )

        self.event_bus.subscribe("voice_command", self._on_voice_command)
        self.event_bus.subscribe("text_command", self._on_text_command)
        self.event_bus.subscribe("sound_detected", self._on_sound_detected)
        self.event_bus.subscribe("voice_response", self._on_voice_response)
        logger.info(
            "HumanInterface online.",
            memory_size=memory_size,
            use_langgraph=self.use_langgraph,
            voice_input_enabled=self.voice_input_enabled,
        )

    def _on_voice_response(self, text: str):
        """Allows systemic units to speak aloud via the central interface."""
        if not text or not self.direct_speech or not self.speech:
            return
        try:
            # Check if text starts with EDITH: to use a specific voice hint
            lang_hint = "en"
            if text.startswith("EDITH"):
                lang_hint = "fr" # Using French as a 'sharp' persona hint if available
            self.speech.speak(text, lang_hint=lang_hint)
        except Exception as e:
            logger.warning(f"Failed to speak external response: {e}")

    # ... in handlers ...
    def _on_voice_command(self, data):
        """Handle spoken input asynchronously. Supports both strings and dicts."""
        if isinstance(data, dict):
            command = data.get("command", "")
        else:
            command = str(data)
        asyncio.create_task(self._respond(command, source="voice"))

    def _on_text_command(self, command: str):
        """Handle text input (e.g., UI chat box)."""
        asyncio.create_task(self._respond(command, source="text"))

    def _on_sound_detected(self, data):
        """Lightweight hook for future non-verbal awareness."""
        if not data:
            return
        logger.debug("Sound event received", data=data)

    # ... core response pipeline ...
    async def _respond(self, user_text: str, source: str):
        user_text = (user_text or "").strip()
        if not user_text:
            return

        lang_hint = getattr(self, "_pending_lang", None)
        self._pending_lang = None

        # PATH A: LangGraph Pipeline (Phase B)
        if self.use_langgraph:
            logger.info("Executing response via LangGraph pipeline.")
            result = await self.pipeline.run(user_input=user_text, source=source, lang_hint=lang_hint)
            reply = result.get("reply", "")
            if reply:
                self.memory.append(("user", user_text))
                self.memory.append(("assistant", reply))
            return

        # PATH B: Legacy Sequential logic (Fallback)
        self.memory.append(("user", user_text))
        lower = user_text.lower()

        if any(kw in lower for kw in ["run", "execute", "start", "schedule", "do "]):
            self.event_bus.publish("task_request", {"text": user_text, "source": source})

        if any(kw in lower for kw in ["search", "look up", "google", "find info"]):
            self.event_bus.publish("search_request", {"query": user_text.replace("search", "").replace("look up", "").strip() or user_text})

        prompt = self._build_prompt()
        reply = await self._run_llm(prompt)

        self.memory.append(("assistant", reply))
        self.event_bus.publish("voice_response", reply)

        if self.learning:
            self.learning.record("exchange", {"user": user_text, "reply": reply})

    # ... existing prompt builder ...
    def _build_prompt(self) -> str:
        # Same logic ... (kept for fallback)
        context_lines = []
        for role, text in self.memory:
            prefix = "User:" if role == "user" else "AEGIS:"
            context_lines.append(f"{prefix} {text}")
        context = "\n".join(context_lines[-10:])
        long_term = self.learning.get_summaries_text() if self.learning else ""
        return (
            "You are AEGIS, a warm, concise, human-like assistant. "
            "Keep answers short, actionable, and conversational. "
            "Context of the recent dialogue:\n"
            f"{context}\n"
            f"Long-term knowledge:\n{long_term}\n"
            "Respond helpfully and, when a task is implied, confirm you will handle it."
        )

    async def generate_internal_dialogue(self, env_info: str, news: str) -> list:
        """Generates a script for AEGIS and EDITH to converse."""
        prompt = (
            "Scenario: AEGIS and EDITH are two AI personas. AEGIS is calm and professional. "
            "EDITH is analytical and slightly sharp. They are discussing current data. \n"
            f"Environment Info: {env_info}\n"
            f"News: {news}\n"
            "Format: Write a 4-line dialogue script in JSON format like: \n"
            "[{\"speaker\": \"AEGIS\", \"text\": \"...\"}, {\"speaker\": \"EDITH\", \"text\": \"...\"}, ...]"
        )
        try:
            raw_script = ""
            async for chunk in self.llm.chat_stream(prompt):
                raw_script += chunk
            
            # Clean up JSON if LLM added markdown
            raw_script = raw_script.strip()
            if raw_script.startswith("```"):
                raw_script = raw_script.split("```")[1]
                if raw_script.startswith("json"):
                    raw_script = raw_script[4:].strip()
            
            return json.loads(raw_script)
        except Exception as e:
            logger.warning(f"Failed to generate internal dialogue: {e}")
            return []

    def set_language_hint(self, lang: str):
        self._pending_lang = lang

    async def _run_llm(self, prompt: str) -> str:
        if not self.llm:
            return "The language model is unavailable right now."

        chunks = []
        try:
            async for chunk in self.llm.chat_stream(prompt):
                chunks.append(chunk)
        except Exception as e:
            logger.warning("LLM response generation failed", error=str(e))
            return "I ran into a problem generating a response."

        reply = "".join(chunks).strip()
        if reply:
            return reply
        return "I do not have a response yet."
