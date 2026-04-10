                      

import importlib
import logging
import threading
import time
import sys
import os
logger = logging.getLogger("AEGIS.SelfHealing")
MODULE_PATH_MAP = {
    "brain": "core.brain",
    "ai": "ai_modules.llm_engine",
    "human_interface": "core.human_interface",
    "voice": "ui.voice_interface",
    "vision": "embodied.vision",
    "task_manager": "core.task_manager",
    "speech": "communication.speech",
    "voice_id": "identity.voice_id",
    "face_id": "identity.face_id",
    "identity": "identity.manager",
    "governance": "governance.policy",
    "health": "health.monitor",
    "dl_core": "deep_learning.core",
    "ml_core": "ml_integration.core",
    "nlp_engine": "ml_integration.nlp",
    "predictor": "ml_integration.predictor",
    "conversation": "conversational_dl.engine",
}
logger.setLevel(logging.INFO)
class SelfHealing:
    def __init__(self, modules: dict):
        self.modules = modules
        self.monitoring = False
    def start_monitoring(self, interval=5):
        self.monitoring = True
        threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True).start()
        logger.info("Self-Healing monitoring started.")
    def _monitor_loop(self, interval):
        while self.monitoring:
            for name, module in self.modules.items():
                if module is None:
                    module_path = MODULE_PATH_MAP.get(name, name)
                    try:
                        mod = importlib.import_module(module_path)
                        self.modules[name] = mod
                        logger.info(f"Module {name} re-initialized successfully.")
                    except Exception as e:
                        logger.warning(f"Cannot re-initialize {name}: {e}")
                elif hasattr(module, "is_alive") and callable(module.is_alive) and module.is_alive() is False:
                    logger.warning(f"Self-Healing: Module {name} crashed. Reloading...")
                    self.reload_module(name)
            time.sleep(interval)
    def reload_module(self, name):
        try:
            module_path = MODULE_PATH_MAP.get(name, name)
            if module_path in sys.modules and sys.modules[module_path] is not None:
                importlib.reload(sys.modules[module_path])
                self.modules[name] = sys.modules[module_path]
                logger.info(f"Module {name} ({module_path}) reloaded successfully.")
            else:
                try:
                    mod = importlib.import_module(module_path)
                    self.modules[name] = mod
                    logger.info(f"Module {name} ({module_path}) loaded successfully.")
                except ImportError as e:
                    logger.warning(f"Cannot reload {name}: module path {module_path} not found ({e}). Module may not be recoverable.")
        except Exception as e:
            logger.error(f"Failed to reload {name}: {e}")
