                      
import logging
import threading
import speech_recognition as sr

logger = logging.getLogger("SATURDAY.Identity.VoiceID")

class VoiceID:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.active = False
        self.recognizer = None
        self.microphone = None
        
        try:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            logger.info("Voice ID initialized")
        except Exception as e:
            logger.warning(f"Speech recognition init failed: {e}")

    def start_listening(self):
        if not self.recognizer:
            logger.warning("Voice recognition not available")
            return
        self.active = True
        threading.Thread(target=self._listen_loop, daemon=True).start()
        logger.info("Voice identification and listening started.")

    def _listen_loop(self):
        if not self.recognizer or not self.microphone:
            return
            
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source)
                while self.active:
                    try:
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                                                                            
                        text = self.recognizer.recognize_google(audio)
                        logger.info(f"Speech recognized: {text}")
                        self.event_bus.publish("voice_command", text)
                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        logger.debug("Speech not understood")
                    except Exception as e:
                        logger.debug(f"Speech recognition error: {e}")
        except Exception as e:
            logger.error(f"Voice listen loop error: {e}")

    def stop_listening(self):
        self.active = False
