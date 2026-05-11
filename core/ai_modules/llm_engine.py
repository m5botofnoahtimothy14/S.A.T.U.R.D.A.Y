                          
import os
import json
import structlog
import asyncio

logger = structlog.get_logger("SATURDAY.AI.LLM")

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
                with open(config_path, 'r') as f:
                    self.config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config for LLMEngine: {e}")
        
        ai_config = self.config.get("ai", {})
        self.use_llama_cpp = ai_config.get("use_llama_cpp", False)
        self.model_path = ai_config.get("model_path", "models/llama-3-8b-instruct.Q4_K_M.gguf")
        self.n_ctx = ai_config.get("n_ctx", 2048)
        self.n_gpu_layers = ai_config.get("n_gpu_layers", -1)
        self.preload = self.strict_prod or os.getenv("SATURDAY_PRELOAD_LLM", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        if self.preload:
            llama = self._get_llama_cpp()
            if not llama and self.strict_prod:
                raise RuntimeError(self._init_error or "LLM backend is unavailable.")

    @property
    def available(self) -> bool:
        return bool(self._get_llama_cpp())
        
    def _get_llama_cpp(self):
        
        if self._llama is None:
            try:
                from llama_cpp import Llama
                if not os.path.exists(self.model_path):
                    self._init_error = f"Llama model file not found: {self.model_path}"
                    logger.warning(self._init_error)
                    return None
                    
                self._llama = Llama(
                    model_path=self.model_path,
                    n_ctx=self.n_ctx,
                    n_gpu_layers=self.n_gpu_layers,
                    verbose=False
                )
                self._init_error = None
                logger.info("llama-cpp model loaded successfully", model=self.model_path)
            except ImportError:
                self._init_error = "llama-cpp-python is not installed."
                logger.error(self._init_error)
                self._llama = False
            except Exception as e:
                self._init_error = f"Failed to initialize llama-cpp: {e}"
                logger.error(self._init_error)
                self._llama = False
        return self._llama

    async def chat_stream(self, prompt: str):
        llama = self._get_llama_cpp()
        if not llama:
            raise RuntimeError(self._init_error or "LLM backend is unavailable.")

        try:
            loop = asyncio.get_event_loop()

            def _run_llama():
                return llama.create_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    stream=True
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
            raise RuntimeError(f"LLM inference failed: {e}") from e
