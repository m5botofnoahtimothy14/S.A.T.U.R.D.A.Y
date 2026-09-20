# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
ROOT = r'D:\S.A.T.U.R.D.A.Y'
PYTHON = os.path.dirname(sys.executable) if sys.executable else r'D:\Python312'

a = Analysis(
    [os.path.join(ROOT, 'saturday_launcher_exe.py')],
    pathex=[ROOT, os.path.join(ROOT, 'core'), PYTHON],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'core', 'ui', 'templates'), 'core/ui/templates'),
        (os.path.join(ROOT, 'core', 'ui', 'static'), 'core/ui/static'),
        (os.path.join(ROOT, 'data'), 'data'),
        (os.path.join(ROOT, '.env'), '.'),
        (os.path.join(ROOT, 'core', 'ui', 'templates'), 'core/ui/templates'),
        (os.path.join(ROOT, 'core', 'ui', 'static'), 'core/ui/static'),
        (os.path.join(PYTHON, 'Lib', 'site-packages', 'faster_whisper', 'assets'), 'faster_whisper/assets'),
    ],
    hiddenimports=[
        'core.engagement',
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'starlette',
        'structlog',
        'psutil',
        'numpy',
        'pydantic',
        'jinja2',
        'aiohttp',
        'requests',
        'paho.mqtt',
        'pystray',
        'PIL',
        'cv2',
        'mediapipe',
        'sounddevice',
        'speech_recognition',
        'pyttsx3',
        'edge_tts',
        'miniaudio',
        'scipy',
        'sklearn',
        'onnxruntime',
        'selenium',
        'firebase_admin',
        'google.auth',
        'google.oauth2',
        'googleapiclient',
        'dotenv',
        'httpx',
        'huggingface_hub',
        'tokenizers',
        'transformers',
        'ctransformers',
        'typing_inspection',
        'pywin32',
        'win32gui',
        'win32con',
        'win32api',
        'win32ts',
        'webbrowser',
        'threading',
        'asyncio',
        'json',
        'logging',
        'hashlib',
        'math',
        'wave',
        'io',
        'base64',
        'importlib',
        'pathlib',
        'signal',
        'gc',
        'shutil',
        'platform',
        'uuid',
        'collections',
        'datetime',
        'time',
        're',
        'os',
        'sys',
        'random',
        'argparse',
        'subprocess',
        'csv',
        'ast',
        'inspect',
        'traceback',
        'textwrap',
        'functools',
        'operator',
        'itertools',
        'copy',
        'pprint',
        'warnings',
        'enum',
        'dataclasses',
        # Core SATURDAY modules
        'core.runtime',
        'core.config',
        'core.state',
        'core.rbac',
        'core.event_bus',
        'core.human_interface',
        'core.cloud_bridge',
        'core.secure_gateway_mount',
        'core.system_tray',
        'core.sound_monitor',
        'core.alert_manager',
        'core.brain',
        'core.greeting',
        'core.spatial_audio',
        'core.visual_overlay',
        'core.window_manager',
        'core.self_heal',
        'core.self_healing',
        'core.admin_mood',
        'core.self_rewrite',
        'core.learning_manager',
        'core.usb_watchdog',
        'core.remote_desktop',
        'core.voice_dl',
        'core.persona',
        'core.task_manager',
        'core.agent_service',
        'core.logging_config',
        # AI modules
        'ai_modules.llm_engine',
        'ai_modules.code_writer',
        'ai_modules.security_assistant',
        'ml_integration.core',
        'ml_integration.predictor',
        'ml_integration.nlp',
        'conversational_dl.engine',
        'deep_learning.core',
        'deep_learning.policy',
        'deep_learning.adaptive',
        'deep_learning.patterns',
        'deep_learning.evolution',
        'deep_learning.backend',
        # Demo showcase (autonomous feature tour)
        'core.demo_showcase',
        # Communication
        'communication.speech',
        'communication.call_agent',
        'communication.livekit_webhooks',
        'communication.livekit_bridge',
        'communication.screen_navigator',
        'communication.social_agent',
        'communication.voice_command_router',
        'communication.whatsapp_navigator',
        'communication.insta_navigator',
        # Services
        'services.web_search',
        'services.music_manager',
        'services.weather_service',
        'services.news_service',
        # Governance
        'governance.policy',
        'governance.consent_manager',
        'governance.privacy_mode',
        'governance.compliance_logger',
        'governance.biometric_policy',
        # Identity
        'identity.manager',
        'identity.face_id',
        'identity.voice_id',
        'identity.voice_biometric',
        # Health
        'health.monitor',
        'health.google_fit_integration',
        'health.sensor_hub',
        'health.fusion',
        'health.fall_prediction',
        'health.doctor_mode',
        'health.rppg_engine',
        # UI
        'ui.bridge',
        'ui.voice_interface',
        'ui.websocket_bridge',
        'ui.notification_handler',
        'ui.edith_voice',
        # Hybrid
        'hybrid.main',
        'hybrid.edith.main',
        'hybrid.edith.task_handler',
        # Distributed
        'distributed',
        'distributed.interdevice_sync',
        # Vision
        'embodied.vision',
        # Christianity
        'christianity_core.spirituality',
        # HomeBot
        'core.homebot_integration',
        'core.homebot.ble_transport',
        'core.homebot.mapping',
        # Sensors
        'core.sensors.wifi_sensing',
        'core.sensors.wifi_thermal',
        'core.sensors.rssi_scan',
        'bleak',
        # Orchestrator
        'orchestrator.showtime_manager',
        # Obsidian
        'obsidian_brain',
        # Integration
        'integration.ros2_bridge',
        'integration.sync_node',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        # torch & tensorflow native pyds hang PyInstaller's isolated import_library /
        # bindepend on this machine (loading _load_dll_libraries / _pywrap_... hangs).
        # Both are guarded with try/except in core.deep_learning.backend, so the frozen
        # app runs and reports torch/tf "off" rather than blocking the build.
        'torch',
        'torch._C',
        'torch.utils',
        'torch.cuda',
        'torch.distributed',
        'torchvision',
        'tensorflow',
        'tensorflow.python',
        'tensorflow_core',
        'keras',
        '_pywrap_tensorflow_common',
        '_pywrap_tensorflow_internal',
        # Heavy optional native stacks that bindepend churns on (large .dll sets) and
        # that are only used behind feature flags / try-except guards in the app:
        # NOTE: ctranslate2 is deliberately NOT excluded - faster_whisper (STT) needs it.
        'mediapipe',
        'onnxruntime',
        # avoid pulling the ML stacks' heavy transitive deps into the frozen package
        'sympy',
        'absl',
        'grpcio',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Bindepend on this machine hangs when the isolated import_library subprocess tries to
# load torch/tensorflow/ctranslate2 native .pyd/.dll files. Even though the Python
# modules are excluded, their DLLs can still leak into a.binaries via transitive hooks.
# Filter them out so the dynamic-lib resolution never touches them, and so the frozen
# app never bundles a dormant torch/TF runtime (both are guarded try/except off).
import re as _re
_DIRTY_NATIVE = _re.compile(
    r"(torch|tensorflow|tensorflow_core|_pywrap_tensorflow|keras|ctranslate2|_rocm_sdk|llama|ggml)",
    _re.IGNORECASE,
)
_cleaned = []
for _b in a.binaries:
    _p = _b[0] if isinstance(_b, tuple) else str(_b)
    if _DIRTY_NATIVE.search(_p):
        continue
    _cleaned.append(_b)
a.binaries = _cleaned

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SATURDAY',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SATURDAY',
)
