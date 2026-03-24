import logging
import time
import threading
import os
from core.event_bus import EventBus
from core.audio_service import CrossPlatformAudio

logger = logging.getLogger("AEGIS.Hybrid.WakeService")


class WakeService:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.running = False
        self.wake_word = "aegis"
        self.secondary_wake_word = "edith"
        self.audio = CrossPlatformAudio()
        self.power_mode = "performance"
        
        logger.info("WakeService initialized", 
                    whisper_ready=self.audio.whisper_model is not None,
                    mic_count=len(self.audio.mics))

    async def listen_for_wake_word(self):
        self.running = True
        logger.info(f"AEGIS LISTENING (OFFLINE DL): '{self.wake_word}'")
        threading.Thread(target=self._run_listener, daemon=True).start()

    def _on_power_mode(self, data):
        self.power_mode = data.get("mode", "performance")

    def _run_listener(self):
        while self.running:
            try:
                with self.audio.mic as source:
                    self.audio.recognizer.adjust_for_ambient_noise(source, duration=1)
                    
                    while self.running:
                        timeout = 2 if self.power_mode == "low" else 0.5
                        try:
                            audio = self.audio.recognizer.listen(source, timeout=timeout, phrase_time_limit=3)
                            text = self.audio.recognize_speech(audio)
                            
                            if text:
                                logger.info(f"STT: {text}")
                                if self.wake_word in text or self.secondary_wake_word in text:
                                    target = "edith" if self.secondary_wake_word in text else "aegis"
                                    logger.info(f"WAKE: {target.upper()}")
                                    self.event_bus.publish("voice_command", {"command": text, "target": target})
                                    
                        except Exception:
                            continue
                            
            except Exception as e:
                logger.error(f"Mic error: {e}")
                time.sleep(1)

    async def stop(self):
        self.running = False
        logger.info("WakeService stopped")
