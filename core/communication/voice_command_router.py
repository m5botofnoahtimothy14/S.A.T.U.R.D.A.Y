# communication/voice_command_router.py

import asyncio
import logging

logger = logging.getLogger("AEGIS.VoiceRouter")

class VoiceCommandRouter:
    def __init__(self, event_bus, speech_engine, whatsapp=None, instagram=None):
        self.event_bus = event_bus
        self.speech = speech_engine
        self.whatsapp = whatsapp
        self.instagram = instagram

    async def process(self, command: str):
        command = command.lower().strip()
        logger.info(f"Processing voice command: {command}")

        if not command:
            return

        # WhatsApp voice control
        if "whatsapp" in command and "message" in command:
            self.speech.speak("WhatsApp messaging active. Use the dashboard to confirm recipients.")
            # We don't block for input() anymore
            return

        # Instagram DM
        if "instagram" in command and "message" in command:
            self.speech.speak("Instagram DM service active.")
            return

        # Default: Send to AI engine for deep processing
        self.event_bus.publish("voice_command_unhandled", {"command": command})
