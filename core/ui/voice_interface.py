# ui/voice_interface.py
import speech_recognition as sr
import pyttsx3
import threading
import structlog
import os
import numpy as np
from core.event_bus import EventBus
from core.audio_service import CrossPlatformAudio

logger = structlog.get_logger("AEGIS.VoiceInterface")


class VoiceInterface:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.wake_word = "aegis"
        self.audio = CrossPlatformAudio()
        self.failure_streak = 0
        self.listening = True
        
        self._init_tts()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _init_tts(self):
        try:
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty('voices')
            for v in voices:
                if "male" in v.name.lower():
                    self.engine.setProperty('voice', v.id)
                    break
            self.engine.setProperty('rate', 160)
            self.engine.setProperty('volume', 1.0)
            logger.info("TTS initialized")
        except Exception as e:
            self.engine = None
            logger.warning("TTS unavailable", error=str(e))

    def _listen_loop(self):
        while self.listening:
            try:
                with self.audio.mic as source:
                    self.audio.recognizer.adjust_for_ambient_noise(source, duration=0.6)
                    logger.info("Voice listener calibrated", threshold=self.audio.recognizer.energy_threshold)
                    
                    while self.listening:
                        try:
                            audio = self.audio.recognizer.listen(source, timeout=3, phrase_time_limit=5)
                            text = self.audio.recognize_speech(audio)
                            
                            if not text:
                                self.failure_streak += 1
                                continue
                            
                            logger.info("Heard", text=text)
                            if self.wake_word in text:
                                text = text.replace(self.wake_word, "", 1).strip()
                            self.event_bus.publish("voice_command", text)
                            self.failure_streak = 0
                            
                        except sr.WaitTimeoutError:
                            self.failure_streak += 1
                            continue
                        except Exception as e:
                            logger.warning("Listen error", error=str(e))
                            self.failure_streak += 1
                            
                        if self.failure_streak >= 5:
                            break
                            
            except Exception as e:
                logger.error("Mic error", error=str(e))
                import time
                time.sleep(1)

    def speak(self, text: str):
        if self.engine:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                logger.warning("TTS error", error=str(e))
