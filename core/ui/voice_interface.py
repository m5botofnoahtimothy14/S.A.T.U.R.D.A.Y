try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

import threading
import structlog
import os
import time
import numpy as np
from core.event_bus import EventBus
from core.audio_service import CrossPlatformAudio

logger = structlog.get_logger("SATURDAY.VoiceInterface")

SATURDAY_VOICE_RATE = 155
SATURDAY_VOICE_VOLUME = 1.0


class VoiceInterface:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.wake_word = "saturday"
        self.audio = CrossPlatformAudio()
        self.failure_streak = 0
        self.listening = True

        self._init_tts()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _init_tts(self):
        try:
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty("voices")
            male_voice = None
            for v in voices:
                name_lower = v.name.lower()
                if "male" in name_lower or "david" in name_lower or "mark" in name_lower:
                    male_voice = v
                    break
            if male_voice:
                self.engine.setProperty("voice", male_voice.id)
            self.engine.setProperty("rate", SATURDAY_VOICE_RATE)
            self.engine.setProperty("volume", SATURDAY_VOICE_VOLUME)
            logger.info(f"TTS initialized: {getattr(male_voice, 'name', 'default')}")
        except Exception as e:
            self.engine = None
            logger.warning("pyttsx3 unavailable, using SpeechManager", error=str(e))

    def _listen_loop(self):
        while self.listening:
            try:
                if not self.audio.mic:
                    logger.info("No microphone available, voice interface in output-only mode")
                    return
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

                            self.failure_streak = 0
                            text_lower = text.lower().strip()

                            if self.wake_word in text_lower:
                                command = text_lower.replace(self.wake_word, "").strip()
                                if command:
                                    self.event_bus.publish("voice_command", {"command": command})
                                else:
                                    self.event_bus.publish("voice_command", {"command": "saturday"})
                            else:
                                self.event_bus.publish("voice_command", {"command": text_lower})

                        except sr.WaitTimeoutError:
                            continue
                        except sr.UnknownValueError:
                            self.failure_streak += 1
                            continue
                        except Exception as e:
                            logger.warning(f"Voice recognition error: {e}")
                            self.failure_streak += 1
                            time.sleep(0.5)

            except Exception as e:
                logger.warning(f"Voice listener error: {e}")
                time.sleep(1)

    def speak(self, text: str):
        if not text:
            return
        if self.engine:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                logger.warning(f"pyttsx3 speak error: {e}")
        else:
            self.event_bus.publish("voice_response", text)

    def stop(self):
        self.listening = False
