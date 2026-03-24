"""
EngagementManager
-----------------
Keeps AEGIS conversational when idle:
- Asks the user lightweight questions after idle time.
- Occasionally triggers a short AEGIS ↔ EDITH banter (simulated via voice_response events).
- Resets timers whenever the user speaks (voice_command).
"""
import asyncio
import random
import time
import structlog

logger = structlog.get_logger("AEGIS.Engagement")


class EngagementManager:
    def __init__(self, event_bus, idle_seconds: int = 120):
        self.event_bus = event_bus
        self.idle_seconds = idle_seconds
        self._last_user_ts = time.time()
        self._running = False

        # Listen for user interaction to reset idle timer
        self.event_bus.subscribe("voice_command", self._on_user_activity)
        self.event_bus.subscribe("text_command", self._on_user_activity)

        self.user_prompts = [
            "How’s your day going? Anything you want me to handle?",
            "Do you want a quick status check or to queue some music?",
            "Need me to draft a plan or remind you about anything?",
            "Shall I run a health check on the system?",
        ]

        self.banter_pairs = [
            ("AEGIS", "EDITH, give me a quick security readout."),
            ("EDITH", "Perimeter nominal. Want me to watch for anomalies?"),
            ("AEGIS", "Great. I can cue some focus music if you like."),
        ]

    def _on_user_activity(self, *_):
        self._last_user_ts = time.time()

    def start(self):
        if self._running:
            return
        self._running = True
        asyncio.create_task(self._loop())
        logger.info("Engagement manager started", idle_seconds=self.idle_seconds)

    async def _loop(self):
        while self._running:
            await asyncio.sleep(10)
            idle = time.time() - self._last_user_ts
            if idle < self.idle_seconds:
                continue

            # Alternate between user prompt and AEGIS↔EDITH banter
            if random.random() < 0.65:
                prompt = random.choice(self.user_prompts)
                self.event_bus.publish("voice_response", prompt)
            else:
                await self._run_banter()

            # reset idle marker to avoid rapid repeats
            self._last_user_ts = time.time()

    async def _run_banter(self):
        # Simulate a short exchange between AEGIS and EDITH without looping forever
        for speaker, line in self.banter_pairs:
            tagged = f"{speaker}: {line}"
            self.event_bus.publish("voice_response", tagged)
            await asyncio.sleep(1.5)
