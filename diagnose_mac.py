#!/usr/bin/env python3
"""SATURDAY - Mac Startup Diagnostic"""
import sys
import platform
print(f"Python: {sys.version}")
print(f"Platform: {platform.platform()}")
print(f"Architecture: {platform.machine()}")
print()

# Check critical imports
modules = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("psutil", "psutil"),
    ("numpy", "numpy"),
    ("cv2", "opencv-python-headless"),
    ("PIL", "Pillow"),
    ("pyttsx3", "pyttsx3"),
    ("speech_recognition", "SpeechRecognition"),
    ("aiohttp", "aiohttp"),
    ("jinja2", "jinja2"),
    ("structlog", "structlog"),
    ("firebase_admin", "firebase-admin"),
    ("torch", "torch"),
    ("tensorflow", "tensorflow"),
    ("pyaudio", "pyaudio"),
    ("pyautogui", "pyautogui"),
    ("mss", "mss"),
    ("sentence_transformers", "sentence-transformers"),
    ("sklearn", "scikit-learn"),
    ("vaderSentiment", "vaderSentiment"),
    ("nltk", "nltk"),
    ("langchain_core", "langchain-core"),
]

print("Module check:")
print("-" * 50)
for mod, pip_name in modules:
    try:
        __import__(mod)
        print(f"✓ {pip_name}")
    except ImportError as e:
        print(f"✗ {pip_name} - {e}")
    except Exception as e:
        print(f"! {pip_name} - {type(e).__name__}: {e}")

print()
print("-" * 50)
print("Attempting to import SATURDAY core modules...")
print("-" * 50)

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

core_modules = [
    "core.main",
    "core.config",
    "core.state",
    "core.event_bus",
    "core.runtime",
    "core.rbac",
    "core.health.monitor",
    "core.governance.policy",
    "core.identity.manager",
    "core.identity.face_id",
    "core.identity.voice_id",
    "core.ai_modules.llm_engine",
    "core.communication.speech",
    "core.embodied.vision",
    "core.ui.bridge",
    "core.ui.voice_interface",
    "core.pipeline",
    "core.greeting",
]

for mod in core_modules:
    try:
        __import__(mod)
        print(f"✓ {mod}")
    except Exception as e:
        print(f"✗ {mod} - {type(e).__name__}: {e}")

print()
print("Done. Check errors above.")
