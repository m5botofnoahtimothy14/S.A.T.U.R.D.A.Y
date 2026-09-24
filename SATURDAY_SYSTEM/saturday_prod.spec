# -*- mode: python ; coding: utf-8 -*-
"""SATURDAY production build — SATURDAY_SYSTEM/main.py, one-dir, console CLI.

Includes everything the unit needs: vault crypto, screen operator + OCR,
agent + local-LLM wiring, senses (onnxruntime stays bundled), ears
(ctranslate2 stays bundled for faster-whisper), dashboard HUD, HomeBot link.

External services (NOT bundled, must exist on the machine):
  Ollama + llama3.2/moondream, Tesseract binary, Mosquitto broker, Core2 HW.
Build:  pyinstaller saturday_prod.spec --noconfirm --clean
Output: dist/SATURDAY/SATURDAY.exe  (run it from its own folder)
"""
import os

from PyInstaller.utils.hooks import collect_data_files

SYS = os.path.dirname(os.path.abspath(SPEC)) if "SPEC" in globals() else os.getcwd()

a = Analysis(
    [os.path.join(SYS, "main.py")],
    pathex=[SYS],
    binaries=[],
    datas=[
        (os.path.join(SYS, "config", "settings.json"), "config"),
        (os.path.join(SYS, "dashboard", "index.html"), "dashboard"),
        (os.path.join(SYS, "models", "emotion-ferplus-8.onnx"), "models"),
        (os.path.join(SYS, ".env.example"), "."),
        (os.path.join(SYS, "README.md"), "."),
    ]
    + collect_data_files("sounddevice")
    + collect_data_files("faster_whisper"),
    hiddenimports=[
        "dotenv",
        "firebase_admin",
        "firebase_admin.credentials",
        "firebase_admin.db",
        "pyautogui",
        "pyscreeze",
        "pymsgbox",
        "pytweening",
        "mouseinfo",
        "PIL",
        "pytesseract",
        "cv2",
        "numpy",
        "scipy",
        "scipy.signal",
        "onnxruntime",
        "sounddevice",
        "faster_whisper",
        "ctranslate2",
        "huggingface_hub",
        "tokenizers",
        "paho.mqtt.client",
        "serial",
        "serial.tools.list_ports",
        "saturday",
        "saturday.saturday_core",
        "saturday.controller",
        "saturday.screen_operator",
        "saturday.agent",
        "saturday.brain",
        "saturday.senses",
        "saturday.ears",
        "saturday.homebot",
        "saturday.dashboard",
        "pmv",
        "pmv.memory_engine",
        "pmv.file_crypto",
        "pmv.deadman",
        "pmv.node_manager",
        "interface",
        "interface.cli",
        "interface.voice",
        "realtime_bridge",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "torch",
        "torchvision",
        "tensorflow",
        "keras",
        "mediapipe",
        "sympy",
        "matplotlib",
        "IPython",
        "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SATURDAY",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="SATURDAY",
)
