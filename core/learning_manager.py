

import json
import os
import threading
from collections import deque
from typing import Any, Dict, Optional
import structlog
logger = structlog.get_logger("SATURDAY.Learning")
class LearningManager:
    def __init__(self, event_bus, llm_engine, task_manager, log_path: str = "data/knowledge.jsonl"):
        self.event_bus = event_bus
        self.llm = llm_engine
        self.task_manager = task_manager
        self.log_path = log_path
        self.buffer = deque(maxlen=50)                     
        self.summaries = deque(maxlen=20)                     
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self._load_existing()
        for evt in ("voice_command", "voice_response", "task_request", "task_failed", "search_results"):
            self.event_bus.subscribe(evt, lambda data, evt=evt: self.record(evt, data))
    def _load_existing(self):
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        obj = json.loads(line)
                        self.buffer.append(obj)
                logger.info("Learning log loaded.", entries=len(self.buffer))
            except Exception as e:
                logger.warning("Failed to load learning log", error=str(e))
    def record(self, event_type: str, payload: Any):
        entry = {"event": event_type, "data": payload}
        self.buffer.append(entry)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to persist learning entry", error=str(e))
        if len(self.buffer) % 10 == 0:
            self.task_manager.schedule(self._summarize_recent(), name="learning_summarize", priority=7)
    async def _summarize_recent(self):
        try:
            items = list(self.buffer)[-12:]
            text_chunks = []
            for item in items:
                text_chunks.append(f"{item['event']}: {str(item['data'])[:400]}")
            prompt = (
                "Summarize these SATURDAY interactions into 3 bullet points of what was learned/observed. "
                "Focus on user preferences, intents, and system issues.\n"
                + "\n".join(text_chunks)
            )
            summary = await self._run_llm(prompt)
            if summary:
                self.summaries.append(summary)
                self.event_bus.publish("knowledge_summary", summary)
                logger.info("Learning summary updated.")
        except Exception as e:
            logger.warning("Learning summarization failed", error=str(e))
    async def _run_llm(self, prompt: str) -> Optional[str]:
        chunks = []
        async for chunk in self.llm.chat_stream(prompt):
            chunks.append(chunk)
        return "".join(chunks).strip() if chunks else None
    def get_summaries_text(self, max_items: int = 3) -> str:
        return "\n".join(list(self.summaries)[-max_items:])
