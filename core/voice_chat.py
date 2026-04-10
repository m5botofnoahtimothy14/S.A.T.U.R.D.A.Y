
import logging
import threading
import queue
import time
import os

from core.audio_service import CrossPlatformAudio
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.VoiceChat")

class VoiceChat:
    def __init__(self, event_bus: EventBus, llm_engine=None, speech_manager=None):
        self.event_bus = event_bus
        self.llm = llm_engine
        self.speech = speech_manager
        self.audio = CrossPlatformAudio()
        self.running = False
        self.listen_thread = None
        self.response_queue = queue.Queue()
        self.greeting_done = False
        
        self.event_bus.subscribe("voice_response", self._on_voice_response)

    def start(self):
        if self.running:
            return
        self.running = True
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        
        if not self.greeting_done:
            time.sleep(0.5)
            self._greet()
            self.greeting_done = True
        
        threading.Thread(target=self._response_loop, daemon=True).start()
        logger.info("VoiceChat started - listening continuously")

    def stop(self):
        self.running = False
        logger.info("VoiceChat stopped")

    def _greet(self):
        greetings = [
            "Hello. I am AEGIS. What can I help you with?",
            "Good day. AEGIS online. What would you like to know?",
            "I am here. What shall we work on today?"
        ]
        import random
        greeting = random.choice(greetings)
        self.speak(greeting)

    def _on_voice_response(self, text):
        if text:
            self.response_queue.put(text)

    def _response_loop(self):
        while self.running:
            try:
                response = self.response_queue.get(timeout=0.5)
                self.speak(response)
            except queue.Empty:
                continue

    def speak(self, text):
        if self.speech:
            self.speech.speak(text)
        elif self.audio.recognizer:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                logger.error(f"TTS error: {e}")

    def _listen_loop(self):
        if not self.audio.recognizer or not self.audio.mic:
            logger.error("Speech recognizer not available")
            return

        while self.running:
            try:
                with self.audio.mic as source:
                    self.audio.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    while self.running:
                        try:
                            audio = self.audio.recognizer.listen(
                                source, 
                                timeout=2, 
                                phrase_time_limit=8
                            )
                            
                            text = self.audio.recognize_speech(audio)
                            
                            if text and len(text) > 1:
                                logger.info(f"You said: {text}")
                                self.event_bus.publish("voice_command", text)
                                
                        except Exception as e:
                            if "timeout" not in str(e).lower():
                                logger.debug(f"Listen: {e}")
                            continue
                            
            except Exception as e:
                logger.error(f"Mic error: {e}")
                time.sleep(1)

def start_voice_chat(event_bus, llm_engine=None, speech_manager=None):
    chat = VoiceChat(event_bus, llm_engine, speech_manager)
    chat.start()
    return chat
