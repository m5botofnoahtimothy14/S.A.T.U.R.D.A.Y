# SATURDAY Environment Configuration
# ===============================
# Local Linux paths (replaces Windows D: drive config)

from pathlib import Path
import os

SATURDAY_ROOT = str(Path(__file__).parent.resolve())
VENV_DIR = os.path.join(SATURDAY_ROOT, ".venv")
PACKAGES_PATH = os.path.join(VENV_DIR, "lib", "python3.12", "site-packages")

# Deep Learning cache directories (local)
CACHE_DIR = os.path.join(SATURDAY_ROOT, ".cache")
TF_HUB_CACHE_DIR = os.path.join(CACHE_DIR, "tensorflow", "hub")
HF_HOME = os.path.join(CACHE_DIR, "huggingface")
TORCH_HOME = os.path.join(CACHE_DIR, "torch")
DEEPFACE_HOME = os.path.join(CACHE_DIR, "deepface")
KERAS_HOME = os.path.join(CACHE_DIR, "keras")
MODELS_DIR = os.path.join(SATURDAY_ROOT, "models")
