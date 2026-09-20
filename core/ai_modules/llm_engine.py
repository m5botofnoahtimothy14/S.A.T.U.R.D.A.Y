import os
import json
import structlog
import asyncio
import random
import time
from datetime import datetime
from pathlib import Path

logger = structlog.get_logger("SATURDAY.AI.LLM")



class BuiltinBrain:
    """Professional fallback brain for SATURDAY when LLMs are offline."""
    
    def __init__(self):
        self.context = []

    def respond(self, user_input: str, persona: str = "SATURDAY") -> str:
        text = user_input.strip().lower()
        if any(w in text for w in ["status", "system", "online"]):
            return f"[{persona}] All core systems are nominal. I am currently operating in fallback mode. Please check Ollama/Llama-cpp connectivity for full reasoning."
        if any(w in text for w in ["hello", "hi", "hey"]):
            return f"[{persona}] Online and ready, Sir. How can I assist your operations today?"
        return f"[{persona}] I've received your input, but my advanced reasoning engine is currently offline. I am operating in basic fallback mode."



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

        def _env_flag(name: str) -> bool:
            return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}

        ai_config = self.config.get("ai", {})
        self.use_llama_cpp = ai_config.get("use_llama_cpp", False) or _env_flag("SATURDAY_USE_LLAMA_CPP")
        self.model_path = ai_config.get("model_path", "models/llama-3-8b-instruct.Q4_K_M.gguf")
        self.backup_models = [
            str(p).strip()
            for p in ai_config.get("backup_models", [])
            if str(p).strip()
        ]
        self.n_ctx = ai_config.get("n_ctx", 2048)
        self.n_gpu_layers = ai_config.get("n_gpu_layers", 0)
        self.preload = self.strict_prod or os.getenv("SATURDAY_PRELOAD_LLM", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        self.use_ollama = ai_config.get("use_ollama", False) or _env_flag("SATURDAY_USE_OLLAMA")
        self.ollama_url = os.getenv("OLLAMA_URL") or ai_config.get("ollama_url", "http://localhost:11434/api/generate")
        self.ollama_model = os.getenv("OLLAMA_MODEL") or ai_config.get("ollama_model", "phi3")

        self._builtin = BuiltinBrain()
        self._use_builtin = not (self.use_llama_cpp or self.use_ollama)

        if self.preload:
            backend_ok = False
            if self.use_ollama and self._check_ollama():
                backend_ok = True
            if not backend_ok and self.use_llama_cpp:
                backend_ok = bool(self._get_llama_cpp())
            if not backend_ok and self.strict_prod:
                raise RuntimeError(self._init_error or "LLM backend is unavailable.")
            if backend_ok:
                self._use_builtin = False

        if self._use_builtin:
            logger.info("Using built-in conversational brain (no local LLM configured)")

    @property
    def available(self) -> bool:
        return True

    def _model_candidates(self) -> list[str]:
        """Ordered list of model paths to try, best-first (tiered backup chain)."""
        candidates: list[str] = []

        def _add(path: str) -> None:
            path = path.strip()
            if path and path not in candidates:
                candidates.append(path)

        _add(self.model_path)
        for backup in self.backup_models:
            _add(backup)

        extra = os.getenv("SATURDAY_MODELS_DIR", "").strip()
        for directory in ("models", extra):
            if not directory:
                continue
            base = Path(directory)
            if not base.is_dir():
                continue
            for match in sorted(base.glob("*.gguf"), key=lambda p: (p.stat().st_size, p.name), reverse=True):
                _add(str(match))
        return candidates

    def _resolve_model_path(self) -> str:
        for candidate in self._model_candidates():
            if os.path.exists(candidate):
                logger.info("Resolved llama-cpp model", model=candidate)
                return candidate
        return self.model_path

    def _get_llama_cpp(self):
        if self._llama is None:
            try:
                from llama_cpp import Llama
            except ImportError:
                self._init_error = "llama-cpp-python is not installed."
                logger.warning(self._init_error)
                self._llama = False
                self._use_builtin = True
                return None

            last_error: Exception | None = None
            for model_path in self._model_candidates():
                if not os.path.exists(model_path):
                    continue
                try:
                    self._llama = Llama(
                        model_path=model_path,
                        n_ctx=self.n_ctx,
                        n_gpu_layers=self.n_gpu_layers,
                        verbose=False,
                    )
                    self._init_error = None
                    self._use_builtin = False
                    logger.info("llama-cpp model loaded successfully", model=model_path)
                    return self._llama
                except Exception as e:
                    last_error = e
                    logger.warning("llama-cpp candidate failed; trying next tier", model=model_path, error=str(e))

            self._init_error = (
                f"All llama-cpp models failed to load: {last_error}"
                if last_error
                else "No llama-cpp GGUF model file found on disk."
            )
            logger.warning(self._init_error)
            self._llama = False
            self._use_builtin = True
        return self._llama

    def _check_ollama(self) -> bool:
        try:
            import requests

            tags_url = self.ollama_url.replace("/api/generate", "/api/tags")
            response = requests.get(tags_url, timeout=2)
            if response.status_code != 200:
                raise RuntimeError(f"Ollama responded {response.status_code}")
            logger.info("Ollama backend reachable", model=self.ollama_model)
            return True
        except Exception as e:
            self._init_error = f"Ollama backend unavailable: {e}"
            logger.warning(self._init_error)
            return False

    async def _stream_ollama(self, prompt: str, persona: str = "SATURDAY"):
        import aiohttp

        payload = {
            "model": self.ollama_model,
            "prompt": f"{BuiltinBrain.PERSONALITY}\nActive persona: {persona}\n\nUser: {prompt}\n\n{persona}:",
            "stream": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.ollama_url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Ollama returned {resp.status}")
                async for raw in resp.content:
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    token = data.get("response") or ""
                    if token:
                        yield token

    async def chat_stream(self, prompt: str, persona: str = "SATURDAY"):
        if self.use_ollama:
            try:
                async for token in self._stream_ollama(prompt, persona):
                    yield token
                return
            except Exception as e:
                logger.warning("Ollama backend failed; falling back", error=str(e))
                self.use_ollama = False

        if self._use_builtin:
            response = self._builtin.respond(prompt, persona)
            for word in response.split():
                yield word + " "
                await asyncio.sleep(0.02)
            return

        llama = self._get_llama_cpp()
        if not llama:
            response = self._builtin.respond(prompt, persona)
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
                            "content": f"{BuiltinBrain.PERSONALITY}\nActive persona: {persona}.",
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
            response = self._builtin.respond(prompt, persona)
            for word in response.split():
                yield word + " "
                await asyncio.sleep(0.02)

    async def chat(self, prompt: str, persona: str = "SATURDAY") -> str:
        chunks = []
        async for chunk in self.chat_stream(prompt, persona):
            chunks.append(chunk)
        return "".join(chunks).strip()
