                             
from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

import numpy as np
import structlog

logger = structlog.get_logger("SATURDAY.ConvDL")

class ConversationMemory:
    def __init__(self, max_memory: int = 1000):
        self.max_memory = max_memory
        self.short_term = deque(maxlen=20)
        self.long_term = deque(maxlen=max_memory)
        self.user_profiles = defaultdict(dict)
        self.facts_learned = {}

    def add_exchange(self, user_msg: str, saturday_msg: str, context: Dict | None = None):
        exchange = {
            "user": user_msg,
            "saturday": saturday_msg,
            "timestamp": time.time(),
            "context": context or {},
        }
        self.short_term.append(exchange)
        self.long_term.append(exchange)

    def get_recent(self, count: int = 10) -> List[Dict]:
        return list(self.short_term)[-count:]

    def learn_fact(self, fact: str, verification: float = 1.0):
        self.facts_learned[fact] = {
            "fact": fact,
            "timestamp": time.time(),
            "verified": verification,
        }

    def get_learned_facts(self) -> List[str]:
        return [fact["fact"] for fact in self.facts_learned.values() if fact["verified"] > 0.5]

class ResponseGenerator:
    def __init__(self):
        self.response_templates = {
            "greeting": [
                "Hello. How can I help?",
                "Hi there. What do you need?",
                "Hello. What should I handle for you?",
            ],
            "acknowledgment": [
                "Understood.",
                "All right.",
                "I see.",
            ],
        }

    def generate(self, intent: str, context: Dict | None = None, user_name: str = "there") -> str:
        templates = self.response_templates.get(intent, self.response_templates["acknowledgment"])
        response = str(np.random.choice(templates))
        return response.replace("{user}", user_name)

class ConversationalDLEngine:
    def __init__(self, event_bus=None, saturday_core=None):
        self.event_bus = event_bus
        self.saturday_core = saturday_core
        self.memory = ConversationMemory()
        self.response_gen = ResponseGenerator()
        self.conversation_active = False
        self.user_name = "there"
        self.last_intent = None
        self.conversation_turns = 0

        self._init_subsystem_connections()
        self._subscribe_to_events()
        logger.info("SATURDAY Conversational DL Engine initialized")

    def _init_subsystem_connections(self):
        self.subsystems = {
            "music": None,
            "calendar": None,
            "email": None,
            "homebot": None,
            "vision": None,
            "security": None,
            "weather": None,
            "search": None,
            "calls": None,
            "messages": None,
        }

    def _subscribe_to_events(self):
        if self.event_bus:
            self.event_bus.subscribe("voice_command_unhandled", self.on_voice_command)
            self.event_bus.subscribe("conversation_start", self.start_conversation)
            self.event_bus.subscribe("conversation_end", self.end_conversation)

    def on_voice_command(self, data):
        try:
            asyncio.create_task(self._handle_voice_command(data))
        except Exception as e:
            logger.warning("Failed to schedule voice conversation", error=str(e))

    async def _handle_voice_command(self, data):
        if isinstance(data, dict):
            command = str(data.get("command", "")).strip()
        else:
            command = str(data or "").strip()

        if not command or command.lower() in {"saturday", "edith"}:
            return

        try:
            result = await self.chat(command, {"source": "voice"})
            response = str(result.get("response", "")).strip()
            if response and self.event_bus:
                self.event_bus.publish("voice_response", response)
        except Exception as e:
            logger.warning("Voice conversation processing failed", error=str(e), command=command)

    def start_conversation(self, data: Dict | None = None):
        self.conversation_active = True
        self.conversation_turns = 0
        greeting = self.response_gen.generate("greeting", {}, self.user_name)
        if self.event_bus:
            self.event_bus.publish("voice_response", greeting)

    def end_conversation(self, data: Dict | None = None):
        self.conversation_active = False
        farewell = str(np.random.choice(["Talk to you later.", "See you soon.", "Goodbye.", "Take care."]))
        if self.event_bus:
            self.event_bus.publish("voice_response", farewell)

    async def chat(self, user_input: str, context: Dict | None = None) -> Dict[str, Any]:
        self.conversation_turns += 1
        processed = self._preprocess_input(user_input)
        intent = self._classify_intent(processed)
        entities = self._extract_entities(processed)

        task_result = None
        if self._requires_action(intent):
            task_result = await self._execute_task(intent, entities, processed)

        response = await self._generate_response(
            intent=intent,
            user_input=user_input,
            entities=entities,
            task_result=task_result,
            context=context,
        )

        self.memory.add_exchange(user_input, response, {"intent": intent, "entities": entities, "turn": self.conversation_turns})
        self._learn_from_conversation(user_input, intent, response)

        return {
            "response": response,
            "intent": intent,
            "entities": entities,
            "task_executed": task_result is not None,
            "task_result": task_result,
            "conversation_turns": self.conversation_turns,
            "saturday_thinking": self._get_thought_process(intent, entities),
        }

    def _preprocess_input(self, text: str) -> str:
        text = text.lower().strip()
        return re.sub(r"[^\w\s\?\!\.\,]", "", text)

    def _classify_intent(self, text: str) -> str:
        text_lower = text.lower()
        intent_patterns = {
            "greeting": ["hello", "hi", "hey", "good morning", "good evening", "howdy"],
            "farewell": ["bye", "goodbye", "see you", "talk later", "gotta go"],
            "music": ["play", "music", "song", "spotify", "pause", "skip", "next", "previous", "volume"],
            "weather": ["weather", "temperature", "forecast", "hot", "cold", "rain", "sunny"],
            "time": ["time", "date", "day", "what day", "what's the date"],
            "search": ["search", "find", "look up", "google", "what is", "who is", "how to"],
            "calendar": ["calendar", "schedule", "meeting", "appointment", "event"],
            "email": ["email", "mail", "send email", "check email", "read email"],
            "call": ["call", "phone", "dial", "contact"],
            "message": ["message", "text", "whatsapp", "sms"],
            "home_control": ["turn", "light", "switch", "smart home", "thermostat", "door", "lock", "unlock", "homebot", "bot"],
            "system": ["status", "system", "check", "how are you", "what can you do"],
            "help": ["help", "help me", "what commands"],
        }

        for intent, keywords in intent_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                return intent

        if "?" in text:
            return "question"
        return "general"

    def _extract_entities(self, text: str) -> Dict[str, Any]:
        entities = {}

        for pattern, value in {"now": "present", "later": "future", "tomorrow": "tomorrow", "today": "today"}.items():
            if pattern in text:
                entities["time"] = value

        for action in ["play", "pause", "stop", "skip", "next", "previous"]:
            if action in text:
                entities["music_action"] = action

        for action in ["on", "off", "open", "close", "lock", "unlock"]:
            if action in text:
                entities["home_action"] = action

        weather_match = re.search(r"(?:weather|forecast|temperature)\s+(?:in|for)\s+(.+)", text)
        if weather_match:
            entities["location"] = weather_match.group(1).strip()

        return entities

    def _requires_action(self, intent: str) -> bool:
        return intent in {
            "music",
            "weather",
            "search",
            "calendar",
            "email",
            "call",
            "message",
            "home_control",
            "system",
        }

    async def _execute_task(self, intent: str, entities: Dict, user_input: str) -> Dict[str, Any] | None:
        task_results = {}

        if intent == "music":
            task_results["music"] = await self._handle_music(entities, user_input)
        if intent == "weather":
            task_results["weather"] = await self._handle_weather(entities)
        if intent == "search":
            task_results["search"] = await self._handle_search(user_input)
        if intent == "calendar":
            task_results["calendar"] = await self._handle_calendar(entities, user_input)
        if intent == "home_control":
            task_results["home"] = await self._handle_home_control(entities, user_input)
        if intent == "system":
            task_results["system"] = await self._handle_system_status()

        return task_results or None

    async def _handle_music(self, entities: Dict, user_input: str) -> Dict:
        action = entities.get("music_action", "play")
        music = getattr(self.saturday_core, "music", None) if self.saturday_core else None
        if not music or not hasattr(music, "play_request"):
            return {"status": "unavailable", "action": action, "reason": "Music service is not configured."}

        query = re.sub(r"\b(play|music|song|spotify|pause|skip|next|previous)\b", "", user_input, flags=re.IGNORECASE).strip()
        try:
            return music.play_request(query=query, action=action)
        except Exception as e:
            logger.warning("Music request failed", error=str(e))
            return {"status": "error", "action": action, "reason": str(e)}

    async def _handle_weather(self, entities: Dict) -> Dict:
        weather_service = getattr(self.saturday_core, "weather_service", None) if self.saturday_core else None
        if not weather_service:
            return {"status": "unavailable", "reason": "Weather service is not configured."}
        try:
            return weather_service.get_current_weather(entities.get("location", ""))
        except Exception as e:
            logger.warning("Weather request failed", error=str(e))
            return {"status": "error", "reason": str(e)}

    async def _handle_search(self, query: str) -> Dict:
        query_clean = query.replace("search", "").replace("find", "").replace("look up", "").strip()
        search_service = getattr(self.saturday_core, "web_search", None) if self.saturday_core else None
        if not search_service or not hasattr(search_service, "search"):
            return {"query": query_clean, "status": "unavailable", "reason": "Search service is not configured."}
        try:
            return {"query": query_clean, "status": "success", "results": search_service.search(query_clean)}
        except Exception as e:
            logger.warning("Search request failed", error=str(e))
            return {"query": query_clean, "status": "error", "reason": str(e)}

    async def _handle_calendar(self, entities: Dict, user_input: str) -> Dict:
        social_agent = getattr(self.saturday_core, "social_agent", None) if self.saturday_core else None
        if not social_agent or not hasattr(social_agent, "check_schedules"):
            return {"status": "unavailable", "reason": "Calendar integration is not configured."}
        try:
            return {"status": "success", "query": user_input, "events": await social_agent.check_schedules()}
        except Exception as e:
            logger.warning("Calendar request failed", error=str(e))
            return {"status": "error", "reason": str(e)}

    async def _handle_home_control(self, entities: Dict, user_input: str) -> Dict:
        action = entities.get("home_action", "on")
        homebot = getattr(self.saturday_core, "homebot", None) if self.saturday_core else None
        if not homebot or not hasattr(homebot, "execute_voice_command"):
            return {"action": action, "status": "unavailable", "reason": "HomeBot integration is not configured."}
        try:
            result = homebot.execute_voice_command(user_input)
            result.setdefault("action", action)
            return result
        except Exception as e:
            logger.warning("Home control request failed", error=str(e))
            return {"action": action, "status": "error", "reason": str(e)}

    async def _handle_system_status(self) -> Dict:
        import psutil

        return {
            "cpu": f"{psutil.cpu_percent()}%",
            "memory": f"{psutil.virtual_memory().percent}%",
            "disk": f"{psutil.disk_usage(os.getenv('SystemDrive', 'C:\\')).percent}%",
        }

    async def _generate_response(
        self,
        intent: str,
        user_input: str,
        entities: Dict,
        task_result: Optional[Dict],
        context: Optional[Dict],
    ) -> str:
        if intent == "greeting":
            return self.response_gen.generate("greeting", context or {}, self.user_name)
        if intent == "farewell":
            return str(np.random.choice(["Bye.", "See you.", "Talk later.", "Take care."]))
        if intent == "help":
            return self._generate_help_response()
        if intent == "question":
            return await self._answer_question(user_input, task_result)
        if task_result:
            return self._format_task_response(intent, task_result)
        return self.response_gen.generate("acknowledgment", context or {}, self.user_name)

    def _generate_help_response(self) -> str:
        return (
            "I can help with music, weather, search, calendar, email, calls, HomeBot, and system status. "
            "Ask directly in natural language."
        )

    async def _answer_question(self, question: str, task_result: Optional[Dict]) -> str:
        if task_result and "search" in task_result:
            return self._format_task_response("search", task_result)
        if "how are you" in question.lower():
            return "I am running and ready to help."
        if "what can you do" in question.lower():
            return self._generate_help_response()
        return "Ask me directly and I will either handle it or tell you what is missing."

    def _format_task_response(self, intent: str, task_result: Dict) -> str:
        if intent == "music":
            music = task_result.get("music", {})
            if music.get("status") == "playing" and music.get("query"):
                return f"Opening music for {music['query']}."
            if music.get("status") == "playing" and music.get("mood"):
                return f"Playing the {music['mood']} playlist."
            if music.get("status") == "stopped":
                return "Music stopped."
            return music.get("reason", "Music is unavailable right now.")

        if intent == "weather":
            weather = task_result.get("weather", {})
            if weather.get("status") == "success":
                return (
                    f"The weather in {weather.get('location', 'that location')} is "
                    f"{weather.get('condition', 'unknown')} at {weather.get('temperature_c', 'N/A')} degrees Celsius."
                )
            return weather.get("reason", "Weather data is unavailable right now.")

        if intent == "search":
            search = task_result.get("search", {})
            results = search.get("results") or []
            if results:
                top = results[0]
                return f"Top result: {top.get('title', 'Unknown')}. {top.get('snippet', '')}".strip()
            return search.get("reason", f"I could not find results for {search.get('query', 'that query')}.")

        if intent == "home_control":
            home = task_result.get("home", {})
            if home.get("status") in {"success", "command_sent"}:
                return home.get("message", "HomeBot command sent.")
            return home.get("reason", "Home control is unavailable right now.")

        if intent == "calendar":
            calendar = task_result.get("calendar", {})
            events = calendar.get("events") or []
            if events:
                first = events[0]
                return f"Your next event is {first.get('task', 'Untitled event')} at {first.get('time', 'an unknown time')}."
            return calendar.get("reason", "Calendar data is unavailable right now.")

        if intent == "system":
            system = task_result.get("system", {})
            return f"System status: CPU {system.get('cpu', 'N/A')}, Memory {system.get('memory', 'N/A')}."

        return "Task completed."

    def _get_thought_process(self, intent: str, entities: Dict) -> str:
        thoughts = [
            f"Processing {intent} intent.",
            "Understanding the request.",
            "Analyzing available subsystems.",
            "Executing the appropriate action.",
        ]
        return str(np.random.choice(thoughts))

    def _learn_from_conversation(self, user_input: str, intent: str, response: str):
        self.last_intent = intent

        if "my name is" in user_input.lower():
            match = re.search(r"my name is (\w+)", user_input.lower())
            if match:
                self.user_name = match.group(1)
                self.memory.user_profiles["current"] = {"name": self.user_name}

        if "remember that" in user_input.lower():
            fact_match = re.search(r"remember that (.+)", user_input.lower())
            if fact_match:
                self.memory.learn_fact(fact_match.group(1))

    def get_conversation_status(self) -> Dict:
        return {
            "active": self.conversation_active,
            "turns": self.conversation_turns,
            "user_name": self.user_name,
            "last_intent": self.last_intent,
            "learned_facts": len(self.memory.get_learned_facts()),
        }
