
import asyncio
import logging
import threading
import queue
import time
import os
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

import structlog
from core.audio_service import CrossPlatformAudio
from core.event_bus import EventBus

logger = structlog.get_logger("AEGIS.VoiceCommand")

PLATFORM = __import__("sys").platform

class Intent(Enum):
    SYSTEM_CONTROL = "system_control"
    VISION = "vision"
    HOME_AUTOMATION = "home_automation"
    COMMUNICATION = "communication"
    MEDIA = "media"
    CODE = "code"
    SECURITY = "security"
    SEARCH = "search"
    FILE = "file"
    CALENDAR = "calendar"
    HEALTH = "health"
    CONVERSATION = "conversation"
    UNKNOWN = "unknown"

@dataclass
class VoiceCommand:
    raw_text: str
    intent: Intent
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    subsystem: str = ""
    action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ConversationContext:
    last_intent: Intent = Intent.UNKNOWN
    last_entities: Dict = field(default_factory=dict)
    pending_action: str = ""
    history: deque = field(default_factory=lambda: deque(maxlen=20))

class SubsystemRouter:
    
    def __init__(self, event_bus: EventBus, llm_engine=None):
        self.event_bus = event_bus
        self.llm = llm_engine
        self.context = ConversationContext()
        
        self.intent_keywords = {
            Intent.SYSTEM_CONTROL: ["restart", "shutdown", "start", "stop", "status", "monitor", "system", "cpu", "memory", "process"],
            Intent.VISION: ["face", "recognize", "camera", "see", "look", "detect", "identify", "vision"],
            Intent.HOME_AUTOMATION: ["light", "fan", "ac", "temperature", "door", "lock", "home", "smart", "automation"],
            Intent.COMMUNICATION: ["send", "message", "email", "call", "whatsapp", "telegram", "sms"],
            Intent.MEDIA: ["play", "pause", "music", "video", "youtube", "spotify", "song", "movie"],
            Intent.CODE: ["code", "program", "debug", "script", "function", "class", "bug", "compile"],
            Intent.SECURITY: ["security", "alert", "intruder", "camera", "motion", "alarm", "surveillance"],
            Intent.SEARCH: ["search", "find", "google", "look up", "browse", "web"],
            Intent.FILE: ["file", "folder", "open", "create", "delete", "download", "save"],
            Intent.CALENDAR: ["calendar", "schedule", "meeting", "reminder", "appointment", "event"],
            Intent.HEALTH: ["health", "heart rate", "temperature", "sleep", "fitness", "exercise"],
            Intent.CONVERSATION: ["what", "how", "why", "who", "when", "tell me", "explain", "help"],
        }
        
        self.subsystem_handlers: Dict[Intent, Callable] = {}
        self._register_handlers()

    def _register_handlers(self):
        self.subsystem_handlers = {
            Intent.SYSTEM_CONTROL: self._handle_system,
            Intent.VISION: self._handle_vision,
            Intent.HOME_AUTOMATION: self._handle_home,
            Intent.COMMUNICATION: self._handle_communication,
            Intent.MEDIA: self._handle_media,
            Intent.CODE: self._handle_code,
            Intent.SECURITY: self._handle_security,
            Intent.SEARCH: self._handle_search,
            Intent.FILE: self._handle_file,
            Intent.CALENDAR: self._handle_calendar,
            Intent.HEALTH: self._handle_health,
            Intent.CONVERSATION: self._handle_conversation,
        }

    def classify_intent(self, text: str) -> tuple[Intent, float, Dict]:
        
        text_lower = text.lower()
        
        scores = {}
        for intent, keywords in self.intent_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            scores[intent] = score
        
        best_intent = max(scores, key=scores.get)
        confidence = scores[best_intent] / max(sum(scores.values()), 1)
        
        entities = self._extract_entities(text_lower, best_intent)
        
        if confidence == 0:
            best_intent = Intent.CONVERSATION
            confidence = 0.5
        
        return best_intent, confidence, entities

    def _extract_entities(self, text: str, intent: Intent) -> Dict:
        entities = {"raw": text}
        
        numbers = [w for w in text.split() if w.isdigit()]
        if numbers:
            entities["numbers"] = numbers
        
        if "camera" in text or "mic" in text:
            for word in text.split():
                if word.isdigit():
                    entities["device_index"] = int(word)
        
        return entities

    async def process_command(self, command: VoiceCommand) -> str:
        
        handler = self.subsystem_handlers.get(command.intent)
        
        if handler:
            response = await handler(command)
        else:
            response = "I can help with that. What would you like me to do?"
        
        self.context.last_intent = command.intent
        self.context.last_entities = command.entities
        self.context.history.append({"intent": command.intent.value, "text": command.raw_text, "response": response[:100]})
        
        return response

    async def _handle_system(self, cmd: VoiceCommand) -> str:
        text = cmd.raw_text.lower()
        
        if "restart" in text:
            self.event_bus.publish("system_restart", {})
            return "Initiating system restart."
        elif "shutdown" in text:
            self.event_bus.publish("system_shutdown", {})
            return "Shutting down AEGIS."
        elif "status" in text or "monitor" in text:
            self.event_bus.publish("system_status", {})
            return "Retrieving system status."
        else:
            return "What system operation would you like me to perform?"

    async def _handle_vision(self, cmd: VoiceCommand) -> str:
        text = cmd.raw_text.lower()
        
        if "face" in text and "recognize" in text:
            self.event_bus.publish("vision_command", {"action": "face_recognition"})
            return "Activating face recognition."
        elif "detect" in text:
            self.event_bus.publish("vision_command", {"action": "object_detection"})
            return "Starting object detection."
        elif "camera" in text:
            cam_idx = cmd.entities.get("device_index", 0)
            self.event_bus.publish("vision_command", {"action": "start_camera", "camera": cam_idx})
            return f"Starting camera {cam_idx}."
        else:
            self.event_bus.publish("vision_command", {"action": "analyze"})
            return "What would you like me to see?"

    async def _handle_home(self, cmd: VoiceCommand) -> str:
        text = cmd.raw_text.lower()
        
        if "light" in text:
            action = "on" if "on" in text else "off" if "off" in text else "toggle"
            self.event_bus.publish("home_command", {"device": "light", "action": action})
            return f"Turning light {action}."
        elif "fan" in text:
            action = "on" if "on" in text else "off" if "off" in text else "toggle"
            self.event_bus.publish("home_command", {"device": "fan", "action": action})
            return f"Fan {action}."
        elif "temperature" in text or "ac" in text:
            self.event_bus.publish("home_command", {"device": "ac", "action": "control"})
            return "Adjusting temperature."
        else:
            return "What home device would you like to control?"

    async def _handle_communication(self, cmd: VoiceCommand) -> str:
        text = cmd.raw_text.lower()
        
        if "whatsapp" in text:
            self.event_bus.publish("comm_command", {"platform": "whatsapp", "action": "send"})
            return "Opening WhatsApp. What message would you like to send?"
        elif "email" in text or "gmail" in text:
            self.event_bus.publish("comm_command", {"platform": "email", "action": "send"})
            return "Preparing email. What should I write?"
        else:
            self.event_bus.publish("comm_command", {"action": "menu"})
            return "How would you like to communicate?"

    async def _handle_media(self, cmd: VoiceCommand) -> str:
        text = cmd.raw_text.lower()
        
        if "play" in text or "pause" in text:
            self.event_bus.publish("media_command", {"action": "play" if "play" in text else "pause"})
            return "Playing media."
        elif "music" in text:
            self.event_bus.publish("media_command", {"action": "music"})
            return "Playing music."
        elif "youtube" in text:
            query = text.replace("youtube", "").replace("play", "").strip()
            self.event_bus.publish("media_command", {"action": "youtube", "query": query})
            return f"Searching YouTube for {query}."
        else:
            return "What media would you like me to play?"

    async def _handle_code(self, cmd: VoiceCommand) -> str:
        text = cmd.raw_text.lower()
        
        if "debug" in text:
            self.event_bus.publish("code_command", {"action": "debug"})
            return "Starting code debugger."
        elif "write" in text or "create" in text:
            self.event_bus.publish("code_command", {"action": "generate"})
            return "What code would you like me to write?"
        elif "explain" in text or "analyze" in text:
            self.event_bus.publish("code_command", {"action": "analyze"})
            return "Paste the code you'd like me to analyze."
        else:
            return "What coding task can I help you with?"

    async def _handle_security(self, cmd: VoiceCommand) -> str:
        text = cmd.raw_text.lower()
        
        if "alert" in text or "alarm" in text:
            self.event_bus.publish("security_command", {"action": "alarm"})
            return "Activating security alarm."
        elif "camera" in text or "surveillance" in text:
            self.event_bus.publish("security_command", {"action": "surveillance"})
            return "Starting security surveillance."
        elif "status" in text:
            self.event_bus.publish("security_status", {})
            return "Checking security status."
        else:
            return "What security measure would you like me to activate?"

    async def _handle_search(self, cmd: VoiceCommand) -> str:
        query = cmd.raw_text.lower().replace("search", "").replace("find", "").replace("google", "").strip()
        self.event_bus.publish("search_request", {"query": query})
        return f"Searching for {query}."

    async def _handle_file(self, cmd: VoiceCommand) -> str:
        text = cmd.raw_text.lower()
        
        if "open" in text:
            self.event_bus.publish("file_command", {"action": "open"})
            return "What file would you like me to open?"
        elif "create" in text:
            self.event_bus.publish("file_command", {"action": "create"})
            return "What file should I create?"
        else:
            return "What file operation do you need?"

    async def _handle_calendar(self, cmd: VoiceCommand) -> str:
        text = cmd.raw_text.lower()
        
        if "schedule" in text or "meeting" in text:
            self.event_bus.publish("calendar_command", {"action": "add"})
            return "What's the meeting about and when?"
        elif "show" in text or "list" in text:
            self.event_bus.publish("calendar_command", {"action": "list"})
            return "Showing your calendar."
        else:
            return "What would you like me to do with your calendar?"

    async def _handle_health(self, cmd: VoiceCommand) -> str:
        self.event_bus.publish("health_command", {"action": "check"})
        return "Checking health metrics."

    async def _handle_conversation(self, cmd: VoiceCommand) -> str:
        if self.llm:
            try:
                async for chunk in self.llm.chat_stream(cmd.raw_text):
                    pass
            except:
                pass
        return "I'm here. What would you like to know or do?"

class VoiceCommandSystem:
    
    def __init__(self, event_bus: EventBus, llm_engine=None, speech_manager=None):
        self.event_bus = event_bus
        self.llm = llm_engine
        self.speech = speech_manager
        self.audio = CrossPlatformAudio()
        self.router = SubsystemRouter(event_bus, llm_engine)
        
        self.running = False
        self.listen_thread = None
        self.speaking = False
        
        self.event_bus.subscribe("voice_response", self._on_response)
        
        logger.info("VoiceCommandSystem initialized",
                   whisper=bool(self.audio.whisper_model),
                   mics=len(self.audio.mics))

    def start(self):
        if self.running:
            return
        self.running = True
        
        self._greet()
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        
        logger.info("VoiceCommandSystem ACTIVE - listening...")

    def stop(self):
        self.running = False
        logger.info("VoiceCommandSystem stopped")

    def _greet(self):
        greetings = [
            "Hello. I am AEGIS. What can I help you with?",
            "AEGIS online. How may I assist you?",
            "I am here. What shall we work on?"
        ]
        import random
        greeting = random.choice(greetings)
        self.speak(greeting)

    def speak(self, text: str):
        if self.speech:
            self.speech.speak(text)
        elif self.audio.recognizer:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except:
                pass

    def _on_response(self, text):
        if text and not self.speaking:
            self.speak(text)

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
                                phrase_time_limit=10
                            )
                            
                            text = self.audio.recognize_speech(audio)
                            
                            if text and len(text) > 1:
                                logger.info(f"VOICE INPUT: {text}")
                                
                                intent, confidence, entities = self.router.classify_intent(text)
                                logger.info(f"INTENT: {intent.value} ({confidence:.2f})")
                                
                                cmd = VoiceCommand(
                                    raw_text=text,
                                    intent=intent,
                                    confidence=confidence,
                                    entities=entities
                                )
                                
                                asyncio.run(self._process_async(cmd))
                                
                        except Exception as e:
                            if "timeout" not in str(e).lower():
                                logger.debug(f"Listen: {e}")
                            continue
                            
            except Exception as e:
                logger.error(f"Mic error: {e}")
                time.sleep(1)

    async def _process_async(self, cmd: VoiceCommand):
        response = await self.router.process_command(cmd)
        if response:
            self.speak(response)

def start_voice_command_system(event_bus, llm_engine=None, speech_manager=None):
    system = VoiceCommandSystem(event_bus, llm_engine, speech_manager)
    system.start()
    return system
