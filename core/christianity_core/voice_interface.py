# voice_interface.py

import asyncio
from .ethical_guidance import EthicalGuidanceEngine
from .scripture_db import ScriptureDB


class VoiceInterface:

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.ethics = EthicalGuidanceEngine()
        self.scripture_db = ScriptureDB()

    async def run(self):
        while True:
            user_input = input("You: ")

            # Ethical evaluation
            ethical_result = self.ethics.evaluate_intent(user_input)

            if not ethical_result["allowed"]:
                print(f"[Ethics] {ethical_result['message']}")
                continue

            # Scripture query trigger
            if "scripture" in user_input.lower():
                verse = self.scripture_db.get_random()
                print(f"{verse['ref']} — {verse['text']}")
                continue

            if "reflect" in user_input.lower():
                print(self.ethics.generate_reflection())
                continue

            self.event_bus.publish("voice_command", user_input)
