import os
import json
import structlog
import asyncio
import random
import time
from datetime import datetime

logger = structlog.get_logger("SATURDAY.AI.LLM")


class BuiltinBrain:
    """Built-in conversational brain when no local LLM is available."""

    PERSONALITY = (
        "You are SATURDAY, a warm, concise, human-like AI assistant. "
        "You speak naturally like a trusted colleague. "
        "Keep responses short and helpful. "
        "You are running on the user's local machine."
    )

    def __init__(self):
        self.context = []
        self.last_topic = None

    def respond(self, user_input: str) -> str:
        text = user_input.strip().lower()
        now = datetime.now()
        hour = now.hour

        greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "howdy", "sup"]
        if any(g in text for g in greetings):
            if hour < 12:
                return random.choice([
                    "Good morning. SATURDAY is online and ready.",
                    "Morning. What can I do for you?",
                    "Hey there. Systems are running smooth. What's up?",
                ])
            elif hour < 17:
                return random.choice([
                    "Hey. SATURDAY here. What do you need?",
                    "Good afternoon. All systems nominal. How can I help?",
                ])
            else:
                return random.choice([
                    "Good evening. SATURDAY is at your service.",
                    "Evening. Everything's running. What can I help with?",
                ])

        if any(w in text for w in ["how are you", "how are you doing", "how's it going", "you good"]):
            return random.choice([
                "All systems running smooth. How can I help you?",
                "I'm doing great, thanks for asking. What do you need?",
                "Running at full capacity. What can I do for you?",
            ])

        if any(w in text for w in ["who are you", "what are you", "your name", "tell me about yourself"]):
            return "I'm SATURDAY, your personal AI operating system. Think of me as your digital assistant - I can help with tasks, answer questions, manage your system, and keep things running smoothly."

        if any(w in text for w in ["what time", "what's the time", "current time", "tell me the time"]):
            return f"It's {now.strftime('%I:%M %p')}."

        if any(w in text for w in ["what date", "what's the date", "today's date", "what day"]):
            return f"Today is {now.strftime('%A, %B %d, %Y')}."

        if any(w in text for w in ["thank", "thanks", "appreciate"]):
            return random.choice([
                "You're welcome. Let me know if you need anything else.",
                "Happy to help.",
                "Anytime.",
            ])

        if any(w in text for w in ["status", "system status", "how's the system", "are you running"]):
            return "All systems are online and running. Voice, web interface, and core modules are active."

        if any(w in text for w in ["help", "what can you do", "capabilities", "features"]):
            return (
                "I can help with quite a bit. Here's what I do: "
                "voice commands, web search, task management, system monitoring, "
                "file operations, communication, and general conversation. "
                "Just ask naturally."
            )

        if any(w in text for w in ["shut down", "shutdown", "turn off", "sleep", "goodbye", "bye"]):
            return "Shutting down gracefully. See you next time."

        if any(w in text for w in ["joke", "funny", "make me laugh"]):
            jokes = [
                "Why do programmers prefer dark mode? Because light attracts bugs.",
                "There are only 10 types of people in the world: those who understand binary and those who don't.",
                "A SQL query walks into a bar, sees two tables and asks: Can I join you?",
                "Why was the JavaScript developer sad? Because he didn't Node how to Express himself.",
            ]
            return random.choice(jokes)

        if any(w in text for w in ["weather", "forecast"]):
            return "I don't have weather data right now, but I can help you check it if you connect a weather service."

        if any(w in text for w in ["music", "play", "song"]):
            return "Music playback is available through the web interface. Want me to help set that up?"

        if any(w in text for w in ["search", "look up", "google", "find"]):
            query = text
            for word in ["search for", "look up", "google", "find"]:
                query = query.replace(word, "").strip()
            return f"I'd search for '{query}' but the web search module needs configuration. Check the web interface for search options."

        if any(w in text for w in ["task", "remind", "schedule", "todo"]):
            return "Task management is available. You can manage tasks through the web interface or tell me what you need scheduled."

        if any(w in text for w in ["run", "execute", "command", "terminal"]):
            return "System commands are available through the web interface dashboard. What specifically do you need executed?"

        if len(text) > 3:
            self.context.append(("user", user_input))
            if len(self.context) > 10:
                self.context = self.context[-10:]

        responses = [
            "Got it. Let me know if you need anything specific.",
            "Understood. What else can I help with?",
            "Noted. Is there something specific you'd like me to do?",
            "I hear you. Let me know how I can assist.",
            "Alright. What would you like me to focus on?",
        ]
        return random.choice(responses)


class LLMEngine:
    def __init__(self, model: str = "llama3"):
        self.model = os.getenv("LLM_MODEL", model)
        self._ollama = None
        self._llama = None
        self._init_error = None
        self.strict_prod = os.getenv("SATURDAY_STRICT_PROD", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        self.config = {}
        config_path = "core/config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    self.config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config for LLMEngine: {e}")

        ai_config = self.config.get("ai", {})
        self.use_llama_cpp = ai_config.get("use_llama_cpp", False)
        self.model_path = ai_config.get("model_path", "models/llama-3-8b-instruct.Q4_K_M.gguf")
        self.n_ctx = ai_config.get("n_ctx", 2048)
        self.n_gpu_layers = ai_config.get("n_gpu_layers", 0)
        self.preload = self.strict_prod or os.getenv("SATURDAY_PRELOAD_LLM", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        self._builtin = BuiltinBrain()
        self._use_builtin = not self.use_llama_cpp

        if self.preload:
            llama = self._get_llama_cpp()
            if not llama and self.strict_prod:
                raise RuntimeError(self._init_error or "LLM backend is unavailable.")

        if self._use_builtin:
            logger.info("Using built-in conversational brain (no local LLM configured)")

    @property
    def available(self) -> bool:
        return True

    def _get_llama_cpp(self):
        if self._llama is None:
            try:
                from llama_cpp import Llama

                if not os.path.exists(self.model_path):
                    self._init_error = f"Llama model file not found: {self.model_path}"
                    logger.warning(self._init_error)
                    self._use_builtin = True
                    return None

                self._llama = Llama(
                    model_path=self.model_path,
                    n_ctx=self.n_ctx,
                    n_gpu_layers=self.n_gpu_layers,
                    verbose=False,
                )
                self._init_error = None
                self._use_builtin = False
                logger.info("llama-cpp model loaded successfully", model=self.model_path)
            except ImportError:
                self._init_error = "llama-cpp-python is not installed."
                logger.warning(self._init_error)
                self._llama = False
                self._use_builtin = True
            except Exception as e:
                self._init_error = f"Failed to initialize llama-cpp: {e}"
                logger.warning(self._init_error)
                self._llama = False
                self._use_builtin = True
        return self._llama

    async def chat_stream(self, prompt: str):
        if self._use_builtin:
            response = self._builtin.respond(prompt)
            for word in response.split():
                yield word + " "
                await asyncio.sleep(0.02)
            return

        llama = self._get_llama_cpp()
        if not llama:
            response = self._builtin.respond(prompt)
            for word in response.split():
                yield word + " "
                await asyncio.sleep(0.02)
            return

        try:
            loop = asyncio.get_event_loop()

            def _run_llama():
                return llama.create_chat_completion(
                    messages=[
                        {
                            "role": "system",
                            "content": BuiltinBrain.PERSONALITY,
                        },
                        {"role": "user", "content": prompt},
                    ],
                    stream=True,
                )

            response = await loop.run_in_executor(None, _run_llama)
            for chunk in response:
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]
            return
        except Exception as e:
            logger.error("Llama-cpp execution failure", error=str(e))
            response = self._builtin.respond(prompt)
            for word in response.split():
                yield word + " "
                await asyncio.sleep(0.02)

    async def chat(self, prompt: str) -> str:
        chunks = []
        async for chunk in self.chat_stream(prompt):
            chunks.append(chunk)
        return "".join(chunks).strip()
