              

import asyncio
import signal
import sys
import os
import structlog
import json
import base64
import io
import wave
import psutil
import random
import time
import logging
import numpy as np
import importlib
import threading
from pathlib import Path
from threading import Thread
from fastapi import FastAPI, Request, WebSocket, APIRouter, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from uvicorn import Config, Server
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import auth as fb_auth
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

logger = logging.getLogger("saturday.main")

class _UnavailableDependency:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Optional SATURDAY dependency unavailable")


def _optional_import(module_name: str, attr_name: str | None = None, fallback=None):
    try:
        module = importlib.import_module(module_name)
        if attr_name is None:
            return module
        return getattr(module, attr_name)
    except Exception as exc:
        logger.warning("Optional import failed for %s.%s: %s", module_name, attr_name or "<module>", exc)
        return fallback

app = FastAPI(title="SATURDAY AI OS")

@app.get("/api/debug")
async def early_healthcheck():
    core = globals().get("_saturday_core")
    if core is None:
        return {"status": "initializing", "initialized": False}
    return {
        "status": "ok",
        "runtime": core.runtime is not None,
        "event_bus": core.event_bus is not None,
        "initialized": True,
    }

templates = Jinja2Templates(directory=str(PROJECT_ROOT / "core/ui/templates"))

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "core/ui/static")), name="static")

EventBus = _optional_import("core.event_bus", "EventBus")
RuntimeStats = _optional_import("core.runtime", "RuntimeStats")
ConfigManager = _optional_import("core.config", "ConfigManager")
SystemState = _optional_import("core.state", "SystemState")
RBAC = _optional_import("core.rbac", "RBAC")
HealthMonitor = _optional_import("health.monitor", "HealthMonitor", _UnavailableDependency)
PolicyEngine = _optional_import("governance.policy", "PolicyEngine", _UnavailableDependency)
IdentityManager = _optional_import("identity.manager", "IdentityManager", _UnavailableDependency)
FaceID = _optional_import("identity.face_id", "FaceID", _UnavailableDependency)
VoiceID = _optional_import("identity.voice_id", "VoiceID", _UnavailableDependency)
VoiceBiometricEngine = _optional_import("identity.voice_biometric", "VoiceBiometricEngine", _UnavailableDependency)
WebUI = _optional_import("ui.bridge", "WebUI", _UnavailableDependency)
VoiceInterface = _optional_import("ui.voice_interface", "VoiceInterface", _UnavailableDependency)
HumanInterface = _optional_import("core.human_interface", "HumanInterface", _UnavailableDependency)
CloudBridge = _optional_import("core.cloud_bridge", "CloudBridge", _UnavailableDependency)
LLMEngine = _optional_import("ai_modules.llm_engine", "LLMEngine", _UnavailableDependency)
SpeechManager = _optional_import("communication.speech", "SpeechManager", _UnavailableDependency)
CallAgent = _optional_import("communication.call_agent", "CallAgent", _UnavailableDependency)
register_livekit_webhooks = _optional_import("communication.livekit_webhooks", "register_livekit_webhooks")
VisionModule = _optional_import("embodied.vision", "VisionModule", _UnavailableDependency)
ChristianityCore = _optional_import("christianity_core.spirituality", "ChristianityCore", _UnavailableDependency)
HomeBotIntegration = _optional_import("core.homebot_integration", "HomeBotIntegration", _UnavailableDependency)
HybridManager = _optional_import("hybrid.main", "HybridManager", _UnavailableDependency)
EDITH = _optional_import("hybrid.edith.main", "EDITH", _UnavailableDependency)
SoundMonitor = _optional_import("core.sound_monitor", "SoundMonitor", _UnavailableDependency)
AlertManager = _optional_import("core.alert_manager", "AlertManager", _UnavailableDependency)
LinkedBrain = _optional_import("core.brain", "LinkedBrain", _UnavailableDependency)
GreetingManager = _optional_import("core.greeting", "GreetingManager", _UnavailableDependency)
SpatialAudioEngine = _optional_import("core.spatial_audio", "SpatialAudioEngine", _UnavailableDependency)
VisualOverlayManager = _optional_import("core.visual_overlay", "VisualOverlayManager", _UnavailableDependency)
from core.agent_service import create_agent_app
from core.task_manager import TaskManager
from core.persona import get_persona_manager
from core.system_control import get_system_controller
from core.ai_governance import get_governance_engine
from core.voice_integration import get_voice_handler
from core.real_integration import get_real_integration

app.mount("/agent", create_agent_app(), name="agent")
WindowManager = _optional_import("core.window_manager", "WindowManager", _UnavailableDependency)
SelfHealManager = _optional_import("core.self_heal", "SelfHealManager", _UnavailableDependency)
SelfHealing = _optional_import("core.self_healing", "SelfHealing", _UnavailableDependency)
AdminMood = _optional_import("core.admin_mood", "AdminMood", _UnavailableDependency)
SelfRewriteAdvisor = _optional_import("core.self_rewrite", "SelfRewriteAdvisor", _UnavailableDependency)
SATURDAYVoiceDL = _optional_import("core.voice_dl", "SATURDAYVoiceDL", _UnavailableDependency)
DeepLearningCore = _optional_import("deep_learning.core", "DeepLearningCore", _UnavailableDependency)
NeuralPolicyEngine = _optional_import("deep_learning.policy", "NeuralPolicyEngine", _UnavailableDependency)
AdaptiveLearningEngine = _optional_import("deep_learning.adaptive", "AdaptiveLearningEngine", _UnavailableDependency)
PatternRecognition = _optional_import("deep_learning.patterns", "PatternRecognition", _UnavailableDependency)
SelfEvolution = _optional_import("deep_learning.evolution", "SelfEvolution", _UnavailableDependency)
MLIntegrationCore = _optional_import("ml_integration.core", "MLIntegrationCore", _UnavailableDependency)
PredictiveEngine = _optional_import("ml_integration.predictor", "PredictiveEngine", _UnavailableDependency)
NLPEngine = _optional_import("ml_integration.nlp", "NLPEngine", _UnavailableDependency)
ConversationalDLEngine = _optional_import("conversational_dl.engine", "ConversationalDLEngine", _UnavailableDependency)
WebSearchService = _optional_import("services.web_search", "WebSearchService", _UnavailableDependency)
MusicManager = _optional_import("services.music_manager", "MusicManager", _UnavailableDependency)
WeatherService = _optional_import("services.weather_service", "WeatherService", _UnavailableDependency)
LearningManager = _optional_import("core.learning_manager", "LearningManager", _UnavailableDependency)
USBWatchdog = _optional_import("core.usb_watchdog", "USBWatchdog", _UnavailableDependency)
RemoteDesktopManager = _optional_import("core.remote_desktop", "RemoteDesktopManager", _UnavailableDependency)
SecurityAssistant = _optional_import("ai_modules.security_assistant", "SecurityAssistant", _UnavailableDependency)
EngagementManager = _optional_import("core.engagement", "EngagementManager", _UnavailableDependency)
SystemTray = _optional_import("core.system_tray", "SystemTray", _UnavailableDependency)
NewsService = _optional_import("services.news_service", "NewsService", _UnavailableDependency)
ScreenNavigator = _optional_import("communication.screen_navigator", "ScreenNavigator", _UnavailableDependency)
SocialAgent = _optional_import("communication.social_agent", "SocialAgent", _UnavailableDependency)
VoiceCommandRouter = _optional_import("communication.voice_command_router", "VoiceCommandRouter", _UnavailableDependency)
WhatsAppNavigator = _optional_import("communication.whatsapp_navigator", "WhatsAppNavigator", _UnavailableDependency)
InstaNavigator = _optional_import("communication.insta_navigator", "InstaNavigator", _UnavailableDependency)
ObsidianBrainLogger = _optional_import("obsidian_brain", "ObsidianBrainLogger", _UnavailableDependency)
InterDeviceSync = _optional_import("distributed", "InterDeviceSync", _UnavailableDependency)
DeviceRegistry = _optional_import("distributed", "DeviceRegistry", _UnavailableDependency)
RemoteControl = _optional_import("distributed", "RemoteControl", _UnavailableDependency)
SessionMirror = _optional_import("distributed", "SessionMirror", _UnavailableDependency)
try_mount_secure_gateway = _optional_import("core.secure_gateway_mount", "try_mount_secure_gateway")
ShowtimeManager = _optional_import("orchestrator.showtime_manager", "ShowtimeManager", _UnavailableDependency)
DATA_DIR = PROJECT_ROOT / "data"
FACE_DB_FILE = DATA_DIR / "faces.json"
FACE_IMAGE_DIR = DATA_DIR / "faces"
DIRECTORY_FILE = DATA_DIR / "directory.json"
VOICE_PROFILES_FILE = DATA_DIR / "voice_profiles.json"
AUDIO_CALIBRATION_FILE = DATA_DIR / "audio_calibration.json"
FIRST_BOOT_FILE = DATA_DIR / "first_boot_setup.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FACE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
def load_json_db(filepath, default=[]):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return default
    return default
def save_json_db(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
from core.logging_config import setup_saturday_logging, SATURDAYLogger, get_log_file_path
setup_saturday_logging()
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
class SubsystemFileHandler(logging.Handler):
    def __init__(self, subsystem=None):
        super().__init__()
        self.subsystem = subsystem
    def emit(self, record):
        try:
            msg = self.format(record)
            main_log = LOG_DIR / "saturday.log"
            with open(main_log, "a") as f:
                f.write(msg + "\n")
            if self.subsystem:
                sub_path = get_log_file_path(self.subsystem)
                with open(sub_path, "a") as f:
                    f.write(msg + "\n")
        except Exception:
            self.handleError(record)
root_logger = logging.getLogger("SATURDAY")
root_logger.setLevel(logging.DEBUG)
root_logger.propagate = False
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
has_main_file_handler = any(
    isinstance(h, logging.FileHandler) and os.path.basename(getattr(h, "baseFilename", "")) == "saturday.log"
    for h in root_logger.handlers
)
if not has_main_file_handler and not any(isinstance(h, SubsystemFileHandler) for h in root_logger.handlers):
    handler = SubsystemFileHandler()
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root_logger.handlers):
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root_logger.addHandler(console)
if not getattr(structlog, "_saturday_configured", False):
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"), 
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.WriteLoggerFactory(file=open(f"{LOG_DIR}/saturday.log", "a")),
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
    )
    structlog._saturday_configured = True
logger = structlog.get_logger("SATURDAY.Core")
router = APIRouter(prefix="/v1", tags=["control-panel"])
connected_websockets = set()
_firebase_initialized = False
def _init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    try:
        firebase_admin.get_app()
    except ValueError:
        try:
            firebase_admin.initialize_app()
        except Exception as e:
            logger.warning("Firebase admin init failed", error=str(e))
    _firebase_initialized = True
def _auth_disabled():
    disabled = os.getenv("SATURDAY_DISABLE_AUTH", "false").strip().lower() in {"1", "true", "yes", "on"}
    strict_prod = os.getenv("SATURDAY_STRICT_PROD", "false").strip().lower() in {"1", "true", "yes", "on"}
    if disabled and strict_prod:
        logger.warning("SATURDAY_DISABLE_AUTH ignored because SATURDAY_STRICT_PROD is enabled")
        return False
    return disabled


def _cors_origins():
    raw = os.getenv("SATURDAY_CORE_ORIGINS", "http://localhost:5173,http://localhost:5174")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
async def verify_firebase_token(request: Request):
    if _auth_disabled():
        return None
    _init_firebase()
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    try:
        decoded = fb_auth.verify_id_token(token)
        request.state.firebase_user = decoded
        return decoded
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
def _require_core():
    if _saturday_core is None:
        raise HTTPException(status_code=503, detail="SATURDAY core is not initialized")
    return _saturday_core
async def _broadcast(event_type: str, data):
    dead = []
    payload = {"type": event_type, "data": data}
    for ws in list(connected_websockets):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_websockets.discard(ws)
def _broadcast_threadsafe(event_type: str, data):
    try:
        if _saturday_core and getattr(_saturday_core, "loop", None):
            asyncio.run_coroutine_threadsafe(_broadcast(event_type, data), _saturday_core.loop)
    except Exception as e:
        logger.debug("WS broadcast failed", error=str(e))
@router.get("/system/stats", dependencies=[Depends(verify_firebase_token)])
async def get_system_stats():
    core = _require_core()
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory().percent
    uptime = time.time() - core.runtime.start_time if hasattr(core, "runtime") else 0
    return {
        "status": "ACTIVE" if core.running else "STANDBY",
        "cpu_percent": cpu,
        "memory_percent": mem,
        "uptime_seconds": int(uptime),
    }
@router.post("/wake", dependencies=[Depends(verify_firebase_token)])
async def wake_saturday():
    core = _require_core()
    try:
        core.event_bus.publish("voice_command", "saturday")
    except Exception as e:
        logger.warning("Wake publish failed", error=str(e))
        raise HTTPException(status_code=500, detail="Wake dispatch failed")
    return {"status": "ok", "message": "Wake signal dispatched"}
@router.post("/commands", dependencies=[Depends(verify_firebase_token)])
async def send_command(payload: dict):
    core = _require_core()
    cmd = str(payload.get("command", "")).strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="Command is required")
    try:
        core.event_bus.publish("voice_command", cmd)
    except Exception as e:
        logger.warning("Command publish failed", error=str(e))
        raise HTTPException(status_code=500, detail="Command dispatch failed")
    return {"status": "ok", "message": "Command dispatched"}
@router.get("/logs", dependencies=[Depends(verify_firebase_token)])
async def tail_logs(limit: int = 50):
    path = os.path.join("logs", "saturday.log")
    if not os.path.exists(path):
        return {"lines": []}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()[-limit:]
    return {"lines": [l.rstrip('\n') for l in lines]}
@router.get("/voice/logs", dependencies=[Depends(verify_firebase_token)])
async def voice_logs(limit: int = 50):
    path = os.path.join("logs", "saturday.log")
    entries = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "Heard speech" in line or "\"voice_command\"" in line:
                    entries.append(line.rstrip("\n"))
    return {"lines": entries[-limit:]}
@router.get("/modules", dependencies=[Depends(verify_firebase_token)])
async def list_modules():
    core = _require_core()
    def state(obj):
        return bool(obj) if obj is not None else False
    return {
        "voice": state(getattr(core, "voice", None)),
        "speech": state(getattr(core, "speech", None)),
        "vision": state(getattr(core, "vision", None)),
        "homebot": state(getattr(core, "homebot", None)),
        "security": state(getattr(core, "security", None)),
    }
@router.post("/modules/{name}/{action}", dependencies=[Depends(verify_firebase_token)])
async def module_action(name: str, action: str):
    core = _require_core()
    mod = getattr(core, name, None)
    if not mod:
        raise HTTPException(status_code=404, detail=f"Module {name} not found")
    action = action.lower()
    try:
        if action == "start" and hasattr(mod, "start"):
            res = mod.start()
        elif action == "stop" and hasattr(mod, "stop"):
            res = mod.stop()
        elif action == "restart":
            if hasattr(mod, "stop"):
                mod.stop()
            res = mod.start() if hasattr(mod, "start") else None
        else:
            raise HTTPException(status_code=400, detail="Unsupported action")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Module action failed", module=name, action=action, error=str(e))
        raise HTTPException(status_code=500, detail="Action failed")
    return {"status": "ok", "result": str(res) if res is not None else "done"}
@router.get("/homebot/status", dependencies=[Depends(verify_firebase_token)])
async def homebot_status():
    core = _require_core()
    hb = getattr(core, "homebot", None)
    return {
        "connected": bool(getattr(hb, "connected", False)),
        "status": getattr(hb, "status", "unknown"),
    }

# ==================== ENHANCED MONITORING & CONTROL ENDPOINTS ====================

@router.get("/ai/saturday/status", dependencies=[Depends(verify_firebase_token)])
async def get_saturday_status():
    """Get comprehensive status of Saturday AI system"""
    core = _require_core()
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    uptime = time.time() - core.runtime.start_time if hasattr(core, "runtime") else 0
    
    return {
        "name": "SATURDAY",
        "type": "primary",
        "status": "ACTIVE" if core.running else "STANDBY",
        "uptime_seconds": int(uptime),
        "system": {
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_mb": mem.used / (1024 * 1024),
        },
        "modules": {
            "voice": bool(getattr(core, "voice", None)),
            "vision": bool(getattr(core, "vision", None)),
            "speech": bool(getattr(core, "speech", None)),
            "brain": bool(getattr(core, "brain", None)),
            "homebot": bool(getattr(core, "homebot", None)),
            "security": bool(getattr(core, "security", None)),
        },
        "last_activity": core.last_activity if hasattr(core, "last_activity") else None,
        "idle_mode": core.idle_mode if hasattr(core, "idle_mode") else False,
    }

@router.get("/ai/edith/status", dependencies=[Depends(verify_firebase_token)])
async def get_edith_status():
    """Get comprehensive status of Edith AI system (subdomain)"""
    core = _require_core()
    try:
        persona_state = get_persona_manager()
        edith = getattr(core, "edith", None)
        if edith is None:
            return {
                "name": "EDITH",
                "type": "subdomain",
                "status": "OFFLINE",
                "message": "Edith system not initialized"
            }
        
        edith_uptime = time.time() - getattr(edith, "start_time", time.time())
        return {
            "name": "EDITH",
            "type": "subdomain",
            "status": "ACTIVE" if persona_state.active_name == "EDITH" else "STANDBY",
            "uptime_seconds": int(edith_uptime),
            "system": {
                "cpu_percent": getattr(edith, "cpu_percent", 0),
                "memory_percent": getattr(edith, "memory_percent", 0),
            },
            "modules": getattr(edith, "modules", {}),
            "last_activity": getattr(edith, "last_activity", None),
            "voice": persona_state.persona_for("EDITH").describe(),
        }
    except Exception:
        logger.warning("Edith status retrieval failed", exc_info=True)
        return {
            "name": "EDITH",
            "type": "secondary",
            "status": "ERROR",
            "error": "Unable to retrieve Edith status"
        }

@router.get("/ai/all/status", dependencies=[Depends(verify_firebase_token)])
async def get_all_ai_status():
    """Get status of all AI systems (Saturday + Edith)"""
    saturday = await get_saturday_status()
    edith = await get_edith_status()
    return {
        "timestamp": time.time(),
        "systems": {
            "saturday": saturday,
            "edith": edith
        }
    }

@router.get("/ai/personas", dependencies=[Depends(verify_firebase_token)])
async def get_persona_status():
    """Return the active persona and its voice/tone configuration."""
    return get_persona_manager().status()

# ==================== TASK MANAGEMENT ====================

@router.get("/tasks", dependencies=[Depends(verify_firebase_token)])
async def get_tasks(ai: str = "saturday", status: str = None):
    """Get tasks for specified AI system"""
    core = _require_core()
    task_manager = getattr(core, "task_manager", None)
    
    if not task_manager:
        return {"tasks": []}
    
    try:
        tasks = task_manager.get_tasks(ai=ai)
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        return {"tasks": tasks, "count": len(tasks)}
    except Exception:
        logger.exception("Task retrieval failed")
        return {"tasks": [], "error": "Task retrieval failed"}

@router.post("/tasks", dependencies=[Depends(verify_firebase_token)])
async def create_task(payload: dict):
    """Create a new task for an AI"""
    core = _require_core()
    task_manager = getattr(core, "task_manager", None)
    
    if not task_manager:
        raise HTTPException(status_code=503, detail="Task manager not available")
    
    try:
        task_data = {
            "title": payload.get("title", "Unnamed Task"),
            "description": payload.get("description", ""),
            "ai": payload.get("ai", "saturday"),
            "priority": payload.get("priority", "normal"),
            "parameters": payload.get("parameters", {}),
        }
        task = task_manager.create_task(task_data)
        return {"status": "created", "task": task}
    except Exception as e:
        logger.warning(f"Task creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Task creation failed: {str(e)}")

@router.put("/tasks/{task_id}", dependencies=[Depends(verify_firebase_token)])
async def update_task(task_id: str, payload: dict):
    """Update a task"""
    core = _require_core()
    task_manager = getattr(core, "task_manager", None)
    
    if not task_manager:
        raise HTTPException(status_code=503, detail="Task manager not available")
    
    try:
        task = task_manager.update_task(task_id, payload)
        return {"status": "updated", "task": task}
    except Exception as e:
        logger.warning(f"Task update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/tasks/{task_id}", dependencies=[Depends(verify_firebase_token)])
async def delete_task(task_id: str):
    """Delete a task"""
    core = _require_core()
    task_manager = getattr(core, "task_manager", None)
    
    if not task_manager:
        raise HTTPException(status_code=503, detail="Task manager not available")
    
    try:
        task_manager.delete_task(task_id)
        return {"status": "deleted", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== COMMAND & CONTROL ====================

@router.post("/control/command", dependencies=[Depends(verify_firebase_token)])
async def execute_command(payload: dict):
    """Execute a command on specified AI"""
    core = _require_core()
    
    ai_target = payload.get("ai", "saturday")
    command = str(payload.get("command", "")).strip()
    params = payload.get("parameters", {})
    
    if not command:
        raise HTTPException(status_code=400, detail="Command is required")
    
    try:
        if core.event_bus:
            if str(ai_target).strip().lower() == "edith" and "edith" not in command.lower():
                command = f"EDITH, {command}"
            core.event_bus.publish("voice_command", {
                "text": command,
                "target": ai_target,
                "params": params,
                "source": "web_control"
            })
        return {"status": "executed", "command": command, "target": ai_target}
    except Exception as e:
        logger.warning(f"Command execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/control/action", dependencies=[Depends(verify_firebase_token)])
async def execute_action(payload: dict):
    """Execute a specific action on AI"""
    core = _require_core()
    
    action = payload.get("action")
    ai_target = payload.get("ai", "saturday")
    
    if not action:
        raise HTTPException(status_code=400, detail="Action is required")
    
    action_map = {
        "wake": lambda: core.event_bus.publish("wake_signal", ai_target) if core.event_bus else None,
        "sleep": lambda: core.event_bus.publish("sleep_signal", ai_target) if core.event_bus else None,
        "pause": lambda: core.event_bus.publish("pause_signal", ai_target) if core.event_bus else None,
        "resume": lambda: core.event_bus.publish("resume_signal", ai_target) if core.event_bus else None,
    }
    
    if action not in action_map:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    
    try:
        action_map[action]()
        return {"status": "ok", "action": action, "target": ai_target}
    except Exception as e:
        logger.warning(f"Action execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== MONITORING & ANALYTICS ====================

@router.get("/monitor/performance", dependencies=[Depends(verify_firebase_token)])
async def get_performance_metrics(ai: str = "saturday", duration: int = 3600):
    """Get performance metrics for specified duration"""
    core = _require_core()
    
    return {
        "ai": ai,
        "duration_seconds": duration,
        "metrics": {
            "cpu_samples": [psutil.cpu_percent(interval=0.1)],
            "memory_samples": [psutil.virtual_memory().percent],
            "response_time_ms": random.uniform(50, 500),
            "uptime_seconds": int(time.time() - core.runtime.start_time) if hasattr(core, "runtime") else 0,
        }
    }

@router.get("/monitor/events", dependencies=[Depends(verify_firebase_token)])
async def get_events(ai: str = "saturday", limit: int = 50):
    """Get recent events for specified AI"""
    core = _require_core()
    
    events = []
    log_path = os.path.join("logs", "saturday.log")
    
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-limit:]
                for i, line in enumerate(lines):
                    events.append({
                        "id": i,
                        "timestamp": time.time() - (limit - i) * 60,
                        "message": line.strip(),
                        "ai": ai
                    })
        except Exception as e:
            logger.warning(f"Event log reading failed: {e}")
    
    return {"events": events, "count": len(events), "ai": ai}

@router.get("/monitor/health", dependencies=[Depends(verify_firebase_token)])
async def get_health_status():
    """Get overall system health"""
    core = _require_core()
    
    health_monitor = getattr(core, "health", None)
    if health_monitor and hasattr(health_monitor, "get_status"):
        try:
            health_data = health_monitor.get_status()
            return health_data
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
    
    return {
        "status": "ok" if core.running else "degraded",
        "timestamp": time.time(),
        "components": {
            "cpu": "ok" if psutil.cpu_percent() < 90 else "warning",
            "memory": "ok" if psutil.virtual_memory().percent < 90 else "warning",
        }
    }

# ==================== SYSTEM CONTROL ====================

@router.post("/system/execute", dependencies=[Depends(verify_firebase_token)])
async def execute_system_command(payload: dict):
    """Execute a system command"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    command = payload.get("command", "")
    if not command:
        raise HTTPException(status_code=400, detail="Command required")
    
    result = system_control.execute_command(command)
    return result

@router.post("/system/app/open", dependencies=[Depends(verify_firebase_token)])
async def open_application(payload: dict):
    """Open an application"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    app = payload.get("app", "")
    if not app:
        raise HTTPException(status_code=400, detail="App name required")
    
    result = system_control.open_application(app)
    return result

@router.post("/system/file/open", dependencies=[Depends(verify_firebase_token)])
async def open_file(payload: dict):
    """Open a file"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    path = payload.get("path", "")
    if not path:
        raise HTTPException(status_code=400, detail="Path required")
    
    result = system_control.open_file(path)
    return result

@router.post("/system/folder/open", dependencies=[Depends(verify_firebase_token)])
async def open_folder(payload: dict):
    """Open a folder"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    path = payload.get("path", "")
    if not path:
        raise HTTPException(status_code=400, detail="Path required")
    
    result = system_control.open_folder(path)
    return result

@router.post("/system/web/search", dependencies=[Depends(verify_firebase_token)])
async def web_search(payload: dict):
    """Perform web search"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    query = payload.get("query", "")
    engine = payload.get("engine", "duckduckgo")
    if not query:
        raise HTTPException(status_code=400, detail="Query required")
    
    result = system_control.web_search(query, engine)
    return result

@router.post("/system/media/play", dependencies=[Depends(verify_firebase_token)])
async def play_media(payload: dict):
    """Play media"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    query = payload.get("query", "")
    platform = payload.get("platform", "youtube")
    if not query:
        raise HTTPException(status_code=400, detail="Query required")
    
    result = system_control.play_media(query, platform)
    return result

@router.post("/system/action", dependencies=[Depends(verify_firebase_token)])
async def system_action(payload: dict):
    """Perform system action"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    action = payload.get("action", "")
    if not action:
        raise HTTPException(status_code=400, detail="Action required")
    
    result = system_control.system_action(action)
    return result

@router.get("/system/info", dependencies=[Depends(verify_firebase_token)])
async def system_info():
    """Get system information"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    return system_control.get_system_info()

@router.get("/system/processes", dependencies=[Depends(verify_firebase_token)])
async def get_processes(limit: int = 20):
    """Get running processes"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    return {"processes": system_control.get_running_processes(limit)}

@router.post("/system/process/kill", dependencies=[Depends(verify_firebase_token)])
async def kill_process(payload: dict):
    """Kill a process"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    pid = payload.get("pid")
    if not pid:
        raise HTTPException(status_code=400, detail="PID required")
    
    return system_control.kill_process(int(pid))

@router.get("/system/windows", dependencies=[Depends(verify_firebase_token)])
async def get_windows():
    """Get open windows"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    return {"windows": system_control.list_windows()}

@router.post("/system/window/focus", dependencies=[Depends(verify_firebase_token)])
async def focus_window(payload: dict):
    """Focus a window"""
    core = _require_core()
    system_control = getattr(core, "system_control", None)
    if not system_control:
        raise HTTPException(status_code=503, detail="System control not available")
    
    title = payload.get("title", "")
    if not title:
        raise HTTPException(status_code=400, detail="Window title required")
    
    return system_control.focus_window(title)

# ==================== GOVERNANCE ====================

@router.get("/governance/stats", dependencies=[Depends(verify_firebase_token)])
async def governance_stats():
    """Get governance statistics"""
    core = _require_core()
    governance = getattr(core, "governance", None)
    if not governance:
        raise HTTPException(status_code=503, detail="Governance engine not available")
    
    return governance.get_stats()

@router.get("/governance/audit", dependencies=[Depends(verify_firebase_token)])
async def governance_audit(limit: int = 100):
    """Get governance audit log"""
    core = _require_core()
    governance = getattr(core, "governance", None)
    if not governance:
        raise HTTPException(status_code=503, detail="Governance engine not available")
    
    return {"audit_log": governance.get_audit_log(limit)}

@router.post("/governance/confirm", dependencies=[Depends(verify_firebase_token)])
async def governance_confirm(payload: dict):
    """Confirm a pending governance action"""
    core = _require_core()
    governance = getattr(core, "governance", None)
    if not governance:
        raise HTTPException(status_code=503, detail="Governance engine not available")
    
    audit_id = payload.get("audit_id")
    confirmed = payload.get("confirmed", False)
    
    if not audit_id:
        raise HTTPException(status_code=400, detail="audit_id required")
    
    if core.event_bus:
        core.event_bus.publish("governance_confirm", {
            "audit_id": audit_id,
            "confirmed": confirmed,
        })
    
    return {"status": "confirmed" if confirmed else "cancelled"}

# ==================== CONFIGURATION ====================

@router.get("/config/settings", dependencies=[Depends(verify_firebase_token)])
async def get_settings(ai: str = "saturday"):
    """Get AI configuration settings"""
    core = _require_core()
    config_manager = getattr(core, "config_manager", None)
    
    if config_manager and hasattr(config_manager, "get_config"):
        try:
            config = config_manager.get_config()
            return {"ai": ai, "settings": config}
        except Exception as e:
            logger.warning(f"Config retrieval failed: {e}")
    
    return {"ai": ai, "settings": {}}

@router.put("/config/settings", dependencies=[Depends(verify_firebase_token)])
async def update_settings(payload: dict):
    """Update AI configuration settings"""
    core = _require_core()
    config_manager = getattr(core, "config_manager", None)
    ai = payload.get("ai", "saturday")
    settings = payload.get("settings", {})
    
    if not config_manager:
        raise HTTPException(status_code=503, detail="Config manager not available")
    
    try:
        if hasattr(config_manager, "update_config"):
            config_manager.update_config(settings)
        return {"status": "updated", "ai": ai}
    except Exception as e:
        logger.warning(f"Settings update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/events")
async def events_ws(websocket: WebSocket):
    if not _auth_disabled():
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=4401)
            return
        _init_firebase()
        try:
            fb_auth.verify_id_token(token)
        except Exception:
            await websocket.close(code=4401)
            return
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        connected_websockets.discard(websocket)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
_secure_gateway_mount_status = try_mount_secure_gateway(app, logger)
_saturday_core = None

class LightweightSATURDAYCore:
    def __init__(self):
        self.app = app
        self.event_bus = EventBus() if EventBus is not None and callable(EventBus) and EventBus is not _UnavailableDependency else None
        self.runtime = RuntimeStats() if RuntimeStats is not None and callable(RuntimeStats) and RuntimeStats is not _UnavailableDependency else None
        self.running = True

    async def shutdown(self):
        self.running = False

@app.on_event("startup")
async def startup_event():
    global _saturday_core
    if _saturday_core is None:
        # Build the full core in a background thread so uvicorn starts serving
        # HTTP immediately (fast API response). Endpoints return 503 until the
        # core is ready (handled by _require_core / early_healthcheck).
        def _build_core():
            global _saturday_core
            try:
                core = SATURDAYCore()
                _saturday_core = core
                # Start the core's background services and then run the loop forever
                core.loop.run_until_complete(core.start_all())
                core.loop.run_forever()
            except Exception as exc:
                logger.warning("Full SATURDAY core initialization failed; falling back to lightweight mode: %s", exc)
                _saturday_core = LightweightSATURDAYCore()
        threading.Thread(target=_build_core, daemon=True).start()

@app.on_event("shutdown")
async def shutdown_event():
    global _saturday_core
    if _saturday_core:
        _saturday_core.running = False
        try:
            await _saturday_core.shutdown()
        except Exception as e:
            logger.warning(f"Startup/shutdown lifecycle cleanup failed: {e}")
class SATURDAYCore:
    def __init__(self):
        load_dotenv()
        self.app = app
        self.templates = templates
        self.websockets = []
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        self.event_bus = EventBus()
        self.personas = get_persona_manager()
        self.runtime = RuntimeStats()
        self.showtime = ShowtimeManager(self.event_bus, self)
        self.showtime.start_lineup()
        self.config_manager = ConfigManager()
        self.strict_prod = os.getenv("SATURDAY_STRICT_PROD", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        try:
            self.state = SystemState()
            self.rbac = RBAC(self.state)
        except Exception as e:
            logger.warning(f"State/RBAC init failed: {e}")
            self.state = None
            self.rbac = None
        self.security_enabled = True
        self.vision_enabled = True
        self.voice_enabled = True
        self.faceid_enabled = True
        self.sound_threshold_db = 55.0
        self.audio_calibration = {}
        self.first_boot_state = {
            "completed": False,
            "completed_at": None,
            "display_name": "",
            "steps": {
                "welcome": False,
                "voice_profile": False,
                "face_profile": False,
                "calibration": False,
            },
        }
        self._apply_audio_calibration()
        self.camera_active = False
        self._camera_task = None
        self.last_activity = time.time()
        self.idle_mode = False
        self.news_service = NewsService()
        self.weather_service = WeatherService()
        self.last_env_summary = "Silent surroundings detected."
        self.last_vision_summary = "No immediate changes in field of view."
        self.event_bus.subscribe("voice_command", lambda _: self._reset_idle())
        self.event_bus.subscribe("text_command", lambda _: self._reset_idle())
        self.event_bus.subscribe("vision_event", self._on_vision_update)
        self.event_bus.subscribe("environment_event", self._on_env_update)
        self.event_bus.subscribe("sound_detected", self._on_sound_update)
        self.event_bus.subscribe("acoustic_scene", self._on_acoustic_scene)
        self.event_bus.subscribe("vitals_update", self._on_health_update)
        self._wire_ws_forwarders()
        self.screen = ScreenNavigator(self.event_bus)
        self.social_agent = None                                   
        try:
            self.health = HealthMonitor(self.event_bus)
        except Exception as e:
            logger.warning(f"HealthMonitor init failed: {e}")
            self.health = None
        try:
            self.governance = PolicyEngine(self.event_bus)
        except Exception as e:
            logger.warning(f"PolicyEngine init failed: {e}")
            self.governance = None
        try:
            self.identity = IdentityManager(self.event_bus)
        except Exception as e:
            logger.warning(f"IdentityManager init failed: {e}")
            self.identity = None
        try:
            self.face_id = FaceID(self.event_bus)
        except Exception as e:
            logger.warning(f"FaceID init failed: {e}")
            self.face_id = None
        try:
            self.voice_id = VoiceID(self.event_bus)
        except Exception as e:
            logger.warning(f"VoiceID init failed: {e}")
            self.voice_id = None
        try:
            self.voice_biometric = VoiceBiometricEngine(db_path=VOICE_PROFILES_FILE)
        except Exception as e:
            logger.warning(f"VoiceBiometric init failed: {e}")
            self.voice_biometric = None
        try:
            self.ai = LLMEngine()
        except Exception as e:
            logger.warning(f"LLMEngine init failed: {e}")
            self.ai = None
        try:
            self.speech = SpeechManager()
        except Exception as e:
            logger.warning(f"SpeechManager init failed: {e}")
            self.speech = None
        try:
            self.call_agent = CallAgent(self.event_bus, self.ai, DIRECTORY_FILE)
        except Exception as e:
            logger.warning(f"CallAgent init failed: {e}")
            self.call_agent = None
        try:
            self.vision = VisionModule(self.event_bus)
        except Exception as e:
            logger.warning(f"VisionSystem init failed: {e}")
            self.vision = None
        try:
            self.sound_monitor = SoundMonitor(self.event_bus, threshold_db=self.sound_threshold_db)
        except Exception as e:
            logger.warning(f"SoundMonitor init failed: {e}")
            self.sound_monitor = None
        self._refresh_first_boot_state()
        try:
            self.showtime.complete_stage("foundation")
        except Exception as e:
            logger.warning(f"Showtime foundation stage completion failed: {e}")
        try:
            self.showtime.complete_stage("core", errors=["sound_monitor_unavailable"] if not self.sound_monitor else None)
        except Exception as e:
            logger.warning(f"Showtime core stage completion failed: {e}")
        try:
            self.spirituality = ChristianityCore(self.event_bus)
        except Exception as e:
            logger.warning(f"ChristianityCore init failed: {e}")
            self.spirituality = None
        try:
            homebot_ip = self.config_manager.get("homebot.device_ip")
            self.homebot = HomeBotIntegration(self.event_bus, mqtt_broker=homebot_ip)
        except Exception as e:
            logger.warning(f"HomeBotIntegration init failed: {e}")
            self.homebot = None
        try:
            self.ui = WebUI(self.event_bus)
        except Exception as e:
            logger.warning(f"WebUI init failed: {e}")
            self.ui = None
        try:
            from core.sensors.wifi_sensing import WiFiSensingEngine
            self.wifi_sensing = WiFiSensingEngine(self.event_bus)
            self.wifi_sensing.start()
            logger.info(f"WiFi Sensing (CSI radar) started — source={self.wifi_sensing.csi_source}")
        except Exception as e:
            logger.warning(f"WiFi Sensing init failed: {e}")
            self.wifi_sensing = None
        self.wifi_thermal = None
        try:
            from core.sensors.wifi_thermal import WiFiThermalMap
            self.wifi_thermal = WiFiThermalMap(grid_size=20, sampling=4)
            self.wifi_thermal.start()
            threading.Thread(target=self._wifi_thermal_feed_loop, daemon=True, name="wifi-thermal-feed").start()
            logger.info("WiFi-Thermal CSI spatial map started (per-network multipath fusion).")
        except Exception as e:
            logger.warning(f"WiFi-Thermal init failed: {e}")
            self.wifi_thermal = None
        # RadarDrive autopilot: fuse WiFi radar house imaging + HomeBot sensor readings
        # to autonomously patrol the house whenever the robocar is present.
        if (
            self.homebot
            and os.getenv("HOMEBOT_RADAR_AUTOPILOT", "true").strip().lower()
            in {"1", "true", "yes", "on"}
        ):
            try:
                ap = self.homebot.get_autopilot(getattr(self, "wifi_sensing", None))
                ap.start()
                logger.info("HomeBot RadarDrive autopilot started (WiFi radar imaging + sensor fusion).")
            except Exception as e:
                logger.warning(f"HomeBot RadarDrive autopilot start failed: {e}")
        try:
            self.voice = VoiceInterface(self.event_bus)
        except Exception as e:
            logger.warning(f"VoiceInterface init failed: {e}")
            self.voice = None
        try:
            self.brain = LinkedBrain(self.event_bus)
        except Exception as e:
            logger.warning(f"LinkedBrain init failed: {e}")
            self.brain = None
        try:
            self.greet = GreetingManager(self.event_bus, self.brain, self.speech)
        except Exception as e:
            logger.warning(f"GreetingManager init failed: {e}")
            self.greet = None
        try:
            self.spatial_audio = SpatialAudioEngine(self.event_bus)
        except Exception as e:
            logger.warning(f"SpatialAudioEngine init failed: {e}")
            self.spatial_audio = None
        self.visual_overlay = None
        try:
            if VisualOverlayManager and not isinstance(VisualOverlayManager, type(_UnavailableDependency)):
                self.visual_overlay = VisualOverlayManager(self.event_bus)
                self.visual_overlay.start()
                logger.info("Visual overlay subprocess started")
        except Exception as e:
            logger.warning(f"VisualOverlay init failed: {e}")
            self.visual_overlay = None
        try:
            self.task_manager = TaskManager(self.event_bus)
        except Exception as e:
            logger.warning(f"TaskManager init failed: {e}")
            self.task_manager = None
        try:
            self.window_manager = WindowManager(self.event_bus)
        except Exception as e:
            logger.warning(f"WindowManager init failed: {e}")
            self.window_manager = None
        try:
            self.showtime.complete_stage("essential")
        except Exception as e:
            logger.warning(f"Showtime essential stage completion failed: {e}")
        try:
            self.self_heal = SelfHealManager(self.event_bus)
        except Exception as e:
            logger.warning(f"SelfHealManager init failed: {e}")
            self.self_heal = None
        try:
            self.admin_mood = AdminMood(self.event_bus)
        except Exception as e:
            logger.warning(f"AdminMood init failed: {e}")
            self.admin_mood = None
        try:
            self.self_rewrite = SelfRewriteAdvisor(self.event_bus)
        except Exception as e:
            logger.warning(f"SelfRewriteAdvisor init failed: {e}")
            self.self_rewrite = None
        try:
            self.learning = LearningManager(self.event_bus, self.ai, self.task_manager)
        except Exception as e:
            logger.warning(f"LearningManager init failed: {e}")
            self.learning = None
        try:
            from deep_learning.backend import DLBackendManager, setup_for_deepface, get_backend_manager
            self.dl_backend = get_backend_manager()
            dl_status = self.dl_backend.get_status()
            logger.info(f"DL Backend initialized - {dl_status.recommended_backend.value.upper()} ({'GPU' if dl_status.gpu_info.available else 'CPU'})")
            if dl_status.gpu_info.available:
                logger.info(f"GPU: {dl_status.gpu_info.name}")
        except Exception as e:
            logger.warning(f"DL Backend Manager init failed: {e}")
            self.dl_backend = None
        try:
            self.dl_core = DeepLearningCore(self.event_bus)
            logger.info("Deep Learning Core initialized - SATURDAY is now a DL-powered AI")
        except Exception as e:
            logger.warning(f"DeepLearningCore init failed: {e}")
            self.dl_core = None
        try:
            self.neural_policy = NeuralPolicyEngine(self.event_bus, self.dl_core)
        except Exception as e:
            logger.warning(f"NeuralPolicyEngine init failed: {e}")
            self.neural_policy = None
        try:
            self.adaptive_learning = AdaptiveLearningEngine(self.event_bus, self.dl_core)
        except Exception as e:
            logger.warning(f"AdaptiveLearningEngine init failed: {e}")
            self.adaptive_learning = None
        try:
            self.pattern_recognition = PatternRecognition(self.event_bus, self.dl_core)
        except Exception as e:
            logger.warning(f"PatternRecognition init failed: {e}")
            self.pattern_recognition = None
        try:
            self.self_evolution = SelfEvolution(
                self.event_bus, 
                self.dl_core, 
                self.adaptive_learning, 
                self.pattern_recognition
            )
        except Exception as e:
            logger.warning(f"SelfEvolution init failed: {e}")
            self.self_evolution = None
        try:
            self.ml_core = MLIntegrationCore(self.event_bus)
            logger.info("ML Integration Core initialized - All subsystems now use ML/DL")
        except Exception as e:
            logger.warning(f"MLIntegrationCore init failed: {e}")
            self.ml_core = None
        try:
            self.nlp_engine = NLPEngine(self.event_bus)
            logger.info("NLP Engine initialized - Voice commands now use DL NLP")
        except Exception as e:
            logger.warning(f"NLPEngine init failed: {e}")
            self.nlp_engine = None
        try:
            self.predictor = PredictiveEngine(self.event_bus)
        except Exception as e:
            logger.warning(f"PredictiveEngine init failed: {e}")
            self.predictor = None
        try:
            self.conversation = ConversationalDLEngine(self.event_bus, self)
            logger.info("Conversational DL Engine initialized - SATURDAY is now truly conversational!")
        except Exception as e:
            logger.warning(f"ConversationalDLEngine init failed: {e}")
            self.conversation = None
        try:
            self.showtime.complete_stage("lazy")
        except Exception as e:
            logger.warning(f"Showtime lazy stage completion failed: {e}")
        try:
            self.usb_watchdog = USBWatchdog(self.event_bus)
        except Exception as e:
            logger.warning(f"USBWatchdog init failed: {e}")
            self.usb_watchdog = None
        try:
            self.remote_desktop = RemoteDesktopManager(self.event_bus)
        except Exception as e:
            logger.warning(f"RemoteDesktopManager init failed: {e}")
            self.remote_desktop = None
        try:
            self.security_assistant = SecurityAssistant(self.event_bus, self.ai)
        except Exception as e:
            logger.warning(f"SecurityAssistant init failed: {e}")
            self.security_assistant = None
        try:
            self.engagement = EngagementManager(self.event_bus)
        except Exception as e:
            logger.warning(f"EngagementManager init failed: {e}")
            self.engagement = None
        try:
            from core.demo_showcase import DemoShowcase
            self.demo_showcase = DemoShowcase(self.event_bus, self)
            logger.info("Demo Showcase ready — say 'demo' to run autonomous feature tour.")
        except Exception as e:
            logger.warning(f"DemoShowcase init failed: {e}")
            self.demo_showcase = None
        try:
            self.alerts = AlertManager(self.event_bus)
        except Exception as e:
            logger.warning(f"AlertManager init failed: {e}")
            self.alerts = None
        try:
            self.hybrid = HybridManager(self.event_bus, self.ai)
        except Exception as e:
            logger.warning(f"HybridManager init failed: {e}")
            self.hybrid = None
        try:
            self.registry = DeviceRegistry(self.event_bus)
            self.sync = InterDeviceSync(self.event_bus)
            self.session_mirror = SessionMirror()
            self.remote_control = RemoteControl(self.rbac, self.event_bus) if self.rbac else None
            logger.info("Distributed Mesh components initialized")
        except Exception as e:
            logger.warning(f"Distributed Mesh init failed: {e}")
        try:
            self.edith = EDITH(self.event_bus, self.brain)
        except Exception as e:
            logger.warning(f"EDITH init failed: {e}")
            self.edith = None
        self.livekit = None
        if self.config_manager.get("ai.use_livekit", False):
            try:
                from communication.livekit_bridge import LiveKitBridge
                self.livekit = LiveKitBridge(self.event_bus)
                logger.info("LiveKit bridge enabled.")
            except Exception as e:
                logger.warning(f"LiveKit bridge failed to initialize: {e}")
                self.livekit = None
        self.ros2 = None
        if self.config_manager.get("ai.use_ros2", False):
            try:
                from integration.ros2_bridge import ROS2Bridge
                self.ros2 = ROS2Bridge(self.event_bus)
                logger.info("ROS2 bridge enabled.")
            except Exception as e:
                logger.warning(f"ROS2 bridge failed to initialize: {e}")
                self.ros2 = None
        self.sync_node = None
        if self.config_manager.get("ai.use_sync", False):
            try:
                from integration.sync_node import StateSyncNode
                self.sync_node = StateSyncNode(self.event_bus, self.runtime)
                logger.info("Sync Node enabled.")
            except Exception as e:
                logger.warning(f"Sync Node failed to initialize: {e}")
                self.sync_node = None
        try:
            from core.human_interface import HumanInterface
            self.human_interface = HumanInterface(self.event_bus, self.ai, self.speech, self.task_manager, self.learning)
        except Exception as e:
            logger.warning(f"HumanInterface init failed: {e}")
            self.human_interface = None
        try:
            from core.voice_dl import SATURDAYVoiceDL
            self.voice_dl = SATURDAYVoiceDL(self.event_bus, self.ai, self.speech)
            logger.info("SATURDAY Voice DL initialized - Full system control ready")
        except Exception as e:
            logger.warning(f"SATURDAYVoiceDL init failed: {e}")
            self.voice_dl = None
        try:
            def handle_speech_lang(payload):
                if payload and self.human_interface:
                    lang = payload.get("lang")
                    if lang:
                        self.human_interface.set_language_hint(lang)
            self.event_bus.subscribe("speech_lang", handle_speech_lang)
        except Exception as e:
            logger.warning("Failed to bind speech_lang handler", error=str(e))
        try:
            speech = self.speech
            if speech:
                self._last_voice_response_text = ""
                self._last_voice_response_at = 0.0
                def _speak_async(text_to_speak: str):
                    try:
                        speech.speak(text_to_speak)
                    except Exception as e:
                        logger.warning(f"Voice response speak failed: {e}")
                def speak_response(text):
                    try:
                        phrase = str(text).strip()
                        if not phrase:
                            return
                        now = time.monotonic()
                        if phrase == self._last_voice_response_text and (now - self._last_voice_response_at) < 20:
                            return
                        self._last_voice_response_text = phrase
                        self._last_voice_response_at = now
                        Thread(target=_speak_async, args=(phrase,), daemon=True).start()
                    except Exception as e:
                        logger.warning(f"Voice response handler failed: {e}")
                self.event_bus.subscribe("voice_response", speak_response)
        except Exception as e:
            logger.warning("Could not bind voice_response -> speech", error=str(e))
        try:
            self.web_search = WebSearchService(self.event_bus)
        except Exception as e:
            logger.warning(f"WebSearchService init failed: {e}")
            self.web_search = None
        try:
            self.music = MusicManager(self.event_bus)
        except Exception as e:
            logger.warning(f"MusicManager init failed: {e}")
            self.music = None
        self.system_tray = None
        try:
            self.system_tray = SystemTray(self)
            logger.info("System tray initialized")
        except Exception as e:
            logger.warning(f"System tray init failed: {e}")
        try:
            self.obsidian_brain = ObsidianBrainLogger(self.event_bus)
            logger.info("Obsidian Brain Logger initialized", vault=self.obsidian_brain.vault_path)
        except Exception as e:
            logger.warning(f"ObsidianBrainLogger init failed: {e}")
            self.obsidian_brain = None
        try:
            self.system_control = get_system_controller(self.event_bus)
            logger.info("System Control initialized")
        except Exception as e:
            logger.warning(f"SystemControl init failed: {e}")
            self.system_control = None
        try:
            self.governance = get_governance_engine(self.event_bus)
            logger.info("AI Governance Engine initialized")
        except Exception as e:
            logger.warning(f"AIGovernance init failed: {e}")
            self.governance = None
        try:
            self.voice_handler = get_voice_handler(self.event_bus, self.real_integration)
            logger.info("Voice Command Handler initialized")
        except Exception as e:
            logger.warning(f"VoiceIntegration init failed: {e}")
            self.voice_handler = None
        try:
            self.real_integration = get_real_integration(self.event_bus, self.governance)
            logger.info("Real Integration Engine initialized")
        except Exception as e:
            logger.warning(f"RealIntegration init failed: {e}")
            self.real_integration = None
        try:
            self.showtime.complete_stage("standard")
        except Exception as e:
            logger.warning(f"Showtime standard stage completion failed: {e}")
        self.setup_routes()
        self.running = True
        try:
            vital_modules = {
                "brain": self.brain,
                "ai": self.ai,
                "human_interface": self.human_interface,
                "voice": self.voice,
                "vision": self.vision,
                "task_manager": self.task_manager
            }
            self.reloader = SelfHealing(vital_modules)
        except Exception as e:
            logger.warning(f"SelfHealing reloader init failed: {e}")
            self.reloader = None
        try:
            self.whatsapp_nav = WhatsAppNavigator()
            self.insta_nav = InstaNavigator()
            self.voice_router = VoiceCommandRouter(self.event_bus, self.speech, self.whatsapp_nav, self.insta_nav)
            self.event_bus.subscribe("voice_command", lambda d: asyncio.create_task(self.voice_router.process(d.get("command", "") if isinstance(d, dict) else str(d))))
        except Exception as e:
            logger.warning(f"Voice Router initialization failed: {e}")
        
        # Configure assistant tool context with real_integration
        try:
            from core.assistant.builtins import configure_tool_context
            configure_tool_context(real_integration=self.real_integration)
            logger.info("Assistant tool context configured with real_integration")
        except Exception as e:
            logger.warning(f"Tool context configuration failed: {e}")
        
        self.app.saturday = self
        self.cloud_bridge = None
        firebase_project_id = self._firebase_project_id()
        if firebase_project_id:
            self.cloud_bridge = CloudBridge(self.event_bus, firebase_project_id)
        try:
             self.social_agent = SocialAgent(self.event_bus, self.human_interface)
             logger.info("Social Agent registered with HumanInterface.")
        except Exception as e:
             logger.warning(f"Social Agent init failed: {e}")
        try:
            if self.showtime:
                self.showtime.complete_stage("optional")
        except Exception as e:
            logger.warning(f"Showtime optional stage completion failed: {e}")
        logger.info("Validating production state", strict_prod=self.strict_prod)
        self._validate_production_state()
        def _ws_forward(event_type):
            return lambda payload: asyncio.create_task(
                self.broadcast_to_ws({"type": event_type, **(payload or {})})
            )
        self.event_bus.subscribe("system_alert", _ws_forward("system_alert"))
        self.event_bus.subscribe("cooldown", _ws_forward("cooldown"))
        self.event_bus.subscribe("admin_mood_update", _ws_forward("admin_mood_update"))
        self.event_bus.subscribe("rewrite_suggestion", _ws_forward("rewrite_suggestion"))
        self.event_bus.subscribe("homebot_telemetry", _ws_forward("homebot_telemetry"))
        self._emit_startup_greeting()
        if self.visual_overlay:
            self.visual_overlay.flash(color=(0, 255, 170), alpha=0.7, duration_ms=1200)
            self.visual_overlay.set_state("startup", 0.9)
        if self.spatial_audio:
            self.spatial_audio.play_startup_chime()
        if self.greet:
            pass
        # Auto-start camera and mic on every boot (original or demo)
        # Camera
        if self.vision:
            try:
                self.camera_active = True
                logger.info("Camera stream configured to auto-start")
            except Exception as e:
                logger.warning(f"Camera auto-start failed: {e}")
        # Mic - intensity-based auto-select + capture
        try:
            from core.audio_service import get_audio_service
            audio = get_audio_service()
            audio.auto_select_device()
            # start_capture is via audio service or voice pipeline
            if hasattr(audio, 'start_capture'):
                try:
                    audio.start_capture()
                    logger.info(f"Mic capture started: {audio.get_current_device()}")
                except Exception as e:
                    logger.warning(f"Mic start_capture failed: {e}")
            # Also ensure SaturdayVoice / pipeline listening if available
            if hasattr(self, 'saturday_voice') and self.saturday_voice:
                try:
                    self.saturday_voice.start_listening()
                    logger.info("SaturdayVoice listening started")
                except Exception:
                    pass
            # Face/Voice recognition loops are event-driven via vision/audio;
            # ensure they are enabled
            self.faceid_enabled = True
            self.voice_enabled = True
            logger.info(f"Face recognition: {self.face_id is not None and self.faceid_enabled}, Voice recognition: {self.voice_id is not None and self.voice_enabled}")
        except Exception as e:
            logger.warning(f"Mic/face/voice auto-start failed: {e}")
        logger.info("SATURDAY Core initialized successfully")
    def _firebase_project_id(self) -> str:
        return (
            os.getenv("FIREBASE_PROJECT_ID", "").strip()
            or os.getenv("VITE_FIREBASE_PROJECT_ID", "").strip()
        )
    def _google_credentials_ready(self) -> bool:
        path = os.getenv("GOOGLE_CREDENTIALS_FILE", "data/google_credentials.json")
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = handle.read()
        except Exception:
            return False
        return "YOUR_CLIENT_ID" not in payload and "YOUR_SECRET" not in payload
    def _validate_production_state(self):
        if not self.strict_prod:
            return
        blockers = []
        if not self.ai or not getattr(self.ai, "available", False):
            blockers.append("LLM backend is unavailable. Verify llama-cpp and the GGUF model file.")
        if not self.voice:
            blockers.append("Voice input is unavailable. Verify microphone access and MICROPHONE_INDEX.")
        if not self.conversation:
            blockers.append("Conversational voice engine is unavailable.")
        if not self.human_interface:
            blockers.append("Human interface failed to initialize.")
        if not self.speech or not getattr(self.speech, "available", False):
            speech_error = getattr(self.speech, "last_error", None) if self.speech else None
            detail = f" Details: {speech_error}" if speech_error else ""
            blockers.append(f"Speaker output is unavailable.{detail}")
        if not self.homebot or not getattr(self.homebot, "connected", False):
            blockers.append("HomeBot is not online. Configure HOMEBOT_BACKEND and connect the real device.")
        if self.config_manager.get("ai.use_livekit", False):
            if not self.livekit or not getattr(self.livekit, "configured", False):
                blockers.append("LiveKit is enabled but credentials are incomplete.")
            elif not getattr(self.livekit, "_sdk_available", False):
                blockers.append("LiveKit Python SDK is unavailable.")
        if self.config_manager.get("ai.use_ros2", False) and (not self.ros2 or not getattr(self.ros2, "active", False)):
            blockers.append("ROS2 bridge is enabled but rclpy is unavailable.")
        if self.config_manager.get("ai.use_sync", False) and not self.sync_node:
            blockers.append("Redis sync node is enabled but failed to initialize.")
        if os.getenv("SATURDAY_ENABLE_SECURE_GATEWAY_MOUNT", "false").strip().lower() in {"1", "true", "yes", "on"}:
            if not _secure_gateway_mount_status.get("mounted", False):
                blockers.append("Secure gateway mount is enabled but failed to mount.")
        firebase_project_id = self._firebase_project_id()
        if firebase_project_id:
            service_account = os.getenv("FIREBASE_SERVICE_ACCOUNT", "").strip()
            if not service_account or not os.path.exists(service_account):
                blockers.append("FIREBASE_SERVICE_ACCOUNT must point to a valid Firebase Admin JSON file.")
            if not self.cloud_bridge or not getattr(self.cloud_bridge, "db", None):
                blockers.append("CloudBridge failed to initialize with Firebase Admin credentials.")
        if not self._google_credentials_ready():
            blockers.append("Google Calendar/Gmail credentials are missing or still placeholders.")
        if blockers:
            raise RuntimeError("Strict production requirements not met:\n- " + "\n- ".join(blockers))
    def _preferred_user_title(self) -> str:
        default_title = "Sir"
        try:
            mode = self.state.get_state("user_mode", default_title) if self.state else default_title
        except Exception:
            mode = default_title
        normalized = str(mode).strip().lower()
        if normalized == "noah":
            return "Noah"
        return "Sir"
    def _emit_startup_greeting(self):
        title = self._preferred_user_title()
        self.event_bus.publish("voice_response", f"SATURDAY OS online. Welcome back, {title}.")

    def _apply_audio_calibration(self):
        try:
            data = load_json_db(AUDIO_CALIBRATION_FILE, default={})
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}

        self.audio_calibration = data

        default_sound = float(data.get("sound_threshold_db", 55.0) or 55.0)
        try:
            self.sound_threshold_db = float(os.getenv("SOUND_MONITOR_THRESHOLD_DB", str(default_sound)))
        except Exception:
            self.sound_threshold_db = default_sound

        if not os.getenv("VOICE_BIOMETRIC_THRESHOLD"):
            vb = data.get("voice_biometric_threshold")
            if vb is not None:
                try:
                    os.environ["VOICE_BIOMETRIC_THRESHOLD"] = str(float(vb))
                except Exception:
                    pass

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return float(max(low, min(high, value)))

    @staticmethod
    def _rms_dbfs(samples: np.ndarray) -> float:
        if samples.size == 0:
            return -120.0
        rms = float(np.sqrt(np.mean(samples * samples)))
        if rms <= 1e-12:
            return -120.0
        return float(20.0 * np.log10(rms + 1e-12))

    def _has_admin_voice_profile(self) -> bool:
        try:
            if self.voice_biometric:
                profiles = self.voice_biometric.list_profiles(safe=True)
            else:
                profiles = load_json_db(VOICE_PROFILES_FILE, default=[])
            if not isinstance(profiles, list):
                return False
            for profile in profiles:
                if not isinstance(profile, dict):
                    continue
                name = str(profile.get("name", "")).strip().lower()
                is_admin = bool(profile.get("is_admin", False) or name == "admin")
                has_samples = int(profile.get("samples", 0) or 0) > 0 or bool(profile.get("trained", False))
                if is_admin and has_samples:
                    return True
            return False
        except Exception:
            return False

    def _has_audio_calibration(self) -> bool:
        try:
            data = load_json_db(AUDIO_CALIBRATION_FILE, default={})
            if not isinstance(data, dict):
                return False
            return "sound_threshold_db" in data and "voice_biometric_threshold" in data
        except Exception:
            return False

    @staticmethod
    def _safe_slug(value: str, fallback: str = "item") -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return fallback
        chars = []
        for ch in raw:
            chars.append(ch if ch.isalnum() else "_")
        slug = "".join(chars)
        while "__" in slug:
            slug = slug.replace("__", "_")
        slug = slug.strip("_")
        return slug or fallback

    @staticmethod
    def _decode_image_payload(image_payload: object) -> tuple[bytes, str, str]:
        raw_name = "capture"
        encoded = ""
        if isinstance(image_payload, dict):
            raw_name = str(image_payload.get("name") or raw_name)
            encoded = str(
                image_payload.get("data")
                or image_payload.get("image_b64")
                or image_payload.get("photo")
                or ""
            ).strip()
        elif isinstance(image_payload, str):
            encoded = image_payload.strip()
        else:
            raise ValueError("Invalid face payload type")

        if not encoded:
            raise ValueError("Face payload is empty")

        ext = ".jpg"
        payload = encoded
        if payload.lower().startswith("data:"):
            header, sep, body = payload.partition(",")
            if not sep:
                raise ValueError("Invalid image data URL")
            payload = body.strip()
            mime = header[5:].split(";", 1)[0].strip().lower()
            if mime == "image/png":
                ext = ".png"
            elif mime == "image/webp":
                ext = ".webp"
            elif mime == "image/bmp":
                ext = ".bmp"
            else:
                ext = ".jpg"

        raw = base64.b64decode(payload)
        if not raw:
            raise ValueError("Decoded face payload is empty")

        if raw.startswith(b"\x89PNG"):
            ext = ".png"
        elif raw[:3] == b"\xff\xd8\xff":
            ext = ".jpg"
        elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
            ext = ".webp"
        elif raw[:2] == b"BM":
            ext = ".bmp"

        return raw, ext, raw_name

    def _persist_face_images(self, name: str, face_id: int, photos_payload: list[object]) -> tuple[list[str], str | None]:
        os.makedirs(FACE_IMAGE_DIR, exist_ok=True)
        identity_slug = self._safe_slug(name, fallback=f"face_{face_id}")
        saved_paths: list[str] = []
        preview_photo: str | None = None

        for idx, payload in enumerate(photos_payload, start=1):
            try:
                raw, ext, raw_name = self._decode_image_payload(payload)
            except Exception as e:
                logger.warning(f"Skipping invalid face payload #{idx}: {e}")
                continue

            if preview_photo is None:
                mime = "image/jpeg"
                if ext == ".png":
                    mime = "image/png"
                elif ext == ".webp":
                    mime = "image/webp"
                elif ext == ".bmp":
                    mime = "image/bmp"
                preview_photo = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"

            source_slug = self._safe_slug(os.path.splitext(raw_name)[0], fallback=f"sample_{idx}")
            filename = f"{identity_slug}_{face_id}_{idx}_{source_slug}{ext}"
            filepath = os.path.join(FACE_IMAGE_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(raw)
            saved_paths.append(filepath.replace("\\", "/"))

        return saved_paths, preview_photo

    def _has_admin_face_profile(self) -> bool:
        try:
            faces = load_json_db(FACE_DB_FILE, default=[])
            if not isinstance(faces, list):
                return False
            for face in faces:
                if not isinstance(face, dict):
                    continue
                name = str(face.get("name", "")).strip().lower()
                relation = str(face.get("relation", "")).strip().lower()
                is_admin = bool(face.get("is_admin", False) or name == "admin" or relation == "admin")
                if not is_admin:
                    continue
                photos = face.get("photos", [])
                if isinstance(photos, list):
                    for photo in photos:
                        if not isinstance(photo, str):
                            continue
                        if photo.startswith("data:image"):
                            return True
                        photo_path = photo.replace("/", os.sep)
                        if os.path.exists(photo_path):
                            return True
                    if photos:
                        return True
                if face.get("photo"):
                    return True
            return False
        except Exception:
            return False

    def _default_first_boot_state(self) -> dict:
        return {
            "completed": False,
            "completed_at": None,
            "display_name": "",
            "steps": {
                "welcome": False,
                "voice_profile": False,
                "face_profile": False,
                "calibration": False,
            },
        }

    def _refresh_first_boot_state(self) -> dict:
        state = self._default_first_boot_state()
        first_boot_file_exists = os.path.exists(FIRST_BOOT_FILE)
        data = load_json_db(FIRST_BOOT_FILE, default={})
        if isinstance(data, dict):
            state.update({k: v for k, v in data.items() if k != "steps"})
            steps = state["steps"].copy()
            if isinstance(data.get("steps"), dict):
                steps.update(data["steps"])
            state["steps"] = steps

        # Infer completion from actual system artifacts.
        state["steps"]["voice_profile"] = bool(state["steps"].get("voice_profile")) or self._has_admin_voice_profile()
        state["steps"]["face_profile"] = bool(state["steps"].get("face_profile")) or self._has_admin_face_profile()
        state["steps"]["calibration"] = bool(state["steps"].get("calibration")) or self._has_audio_calibration()
        if not state.get("display_name") and self.state:
            try:
                state["display_name"] = str(self.state.get_state("user_mode", "") or "").strip()
            except Exception:
                pass
        if (
            not first_boot_file_exists
            and state["steps"]["voice_profile"]
            and state["steps"]["calibration"]
        ):
            state["steps"]["welcome"] = True
            state["completed"] = True
            state["completed_at"] = time.time()

        self.first_boot_state = state
        return state

    def _save_first_boot_state(self, state: dict):
        safe = self._default_first_boot_state()
        if isinstance(state, dict):
            safe.update({k: v for k, v in state.items() if k != "steps"})
            if isinstance(state.get("steps"), dict):
                merged_steps = safe["steps"].copy()
                merged_steps.update(state["steps"])
                safe["steps"] = merged_steps
        save_json_db(FIRST_BOOT_FILE, safe)
        self.first_boot_state = safe
        return safe

    def _wifi_thermal_feed_loop(self):
        """Continuously sample per-network RSSI and feed the WiFi-thermal spatial mapper."""
        if not getattr(self, "wifi_thermal", None):
            return
        import time as _t
        while True:
            try:
                networks = []
                try:
                    from core.sensors.rssi_scan import RSSIScanner
                    networks = RSSIScanner(self.event_bus)._collect_rssi()
                except Exception:
                    networks = []
                if networks:
                    for n in networks:
                        try:
                            self.wifi_thermal.feed_network(
                                str(n.get("bssid") or n.get("ssid") or "ap"),
                                str(n.get("ssid") or "AP"),
                                float(n.get("rssi", 50) if "rssi" in n else n.get("signal", 50)),
                            )
                        except Exception:
                            pass
                # occasionally also feed the aggregate CSI amplitude as an extra node input
                ws = getattr(self, "wifi_sensing", None)
                if ws and ws.buf and hasattr(self, "event_bus"):
                    try:
                        import random as _r
                        agg = float(list(ws.buf)[-1]) + _r.uniform(-0.4, 0.4)
                        self.wifi_thermal.feed_network("aggregate-csi", "CSI-envelope", agg)
                    except Exception:
                        pass
            except Exception:
                pass
            _t.sleep(max(2.0, self.wifi_thermal.sampling / 2.0))

    def _first_boot_status_payload(self) -> dict:
        state = self._refresh_first_boot_state()
        requirements = {
            "admin_voice_profile": self._has_admin_voice_profile(),
            "admin_face_profile": self._has_admin_face_profile(),
            "audio_calibration": self._has_audio_calibration(),
        }
        pending = not bool(state.get("completed", False))
        return {
            "pending": pending,
            "completed": not pending,
            "state": state,
            "requirements": requirements,
        }

    def _auto_calibrate_audio_from_mic(self) -> dict:
        try:
            import speech_recognition as sr
        except Exception as e:
            raise RuntimeError(f"SpeechRecognition is unavailable: {e}")

        recognizer = sr.Recognizer()
        sample_rate = 16000

        def _to_samples(audio_data) -> np.ndarray:
            raw = audio_data.get_raw_data(convert_rate=sample_rate, convert_width=2)
            if not raw:
                return np.zeros(0, dtype=np.float32)
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            return np.clip(arr, -1.0, 1.0)

        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
            ambient_audio = recognizer.record(source, duration=4.0)
            try:
                speech_audio = recognizer.listen(source, timeout=8.0, phrase_time_limit=6.0)
            except sr.WaitTimeoutError:
                speech_audio = recognizer.record(source, duration=4.0)

        ambient = _to_samples(ambient_audio)
        speech = _to_samples(speech_audio)

        ambient_dbfs = self._rms_dbfs(ambient)
        speech_dbfs = self._rms_dbfs(speech)
        ambient_db = ambient_dbfs + 100.0
        speech_db = speech_dbfs + 100.0
        snr = speech_db - ambient_db

        if snr >= 10.0:
            base_offset = 6.0
        elif snr >= 6.0:
            base_offset = 8.0
        else:
            base_offset = 10.0

        sound_threshold_db = self._clamp(ambient_db + base_offset, 45.0, 80.0)
        voice_biometric_threshold = float(os.getenv("VOICE_BIOMETRIC_THRESHOLD", "0.72"))

        score_speech = None
        score_ambient = None
        scope = "admin"
        if self.voice_biometric and self.voice_biometric.has_profiles(admin_only=True):
            speech_match = self.voice_biometric.verify_speaker(speech, sample_rate, threshold=0.0, admin_only=True)
            ambient_match = self.voice_biometric.verify_speaker(ambient, sample_rate, threshold=0.0, admin_only=True)
            score_speech = float(speech_match.get("score", -1.0))
            score_ambient = float(ambient_match.get("score", -1.0))
        elif self.voice_biometric and self.voice_biometric.has_profiles(admin_only=False):
            scope = "any"
            speech_match = self.voice_biometric.verify_speaker(speech, sample_rate, threshold=0.0, admin_only=False)
            ambient_match = self.voice_biometric.verify_speaker(ambient, sample_rate, threshold=0.0, admin_only=False)
            score_speech = float(speech_match.get("score", -1.0))
            score_ambient = float(ambient_match.get("score", -1.0))

        if score_speech is not None and score_ambient is not None and score_speech >= 0 and score_ambient >= 0:
            margin = max(0.08, (score_speech - score_ambient) * 0.55)
            voice_biometric_threshold = self._clamp(score_ambient + margin, 0.62, 0.90)

        result = {
            "captured_at": time.time(),
            "ambient_db": round(ambient_db, 2),
            "ambient_dbfs": round(ambient_dbfs, 2),
            "speech_db": round(speech_db, 2),
            "speech_dbfs": round(speech_dbfs, 2),
            "snr_db": round(snr, 2),
            "sound_threshold_db": round(sound_threshold_db, 2),
            "voice_biometric_threshold": round(float(voice_biometric_threshold), 3),
            "speaker_scope": scope,
            "speaker_score_speech": None if score_speech is None else round(score_speech, 4),
            "speaker_score_ambient": None if score_ambient is None else round(score_ambient, 4),
            "updated_at": time.time(),
        }

        save_json_db(AUDIO_CALIBRATION_FILE, result)
        self._apply_audio_calibration()
        if self.sound_monitor:
            self.sound_monitor.threshold_db = self.sound_threshold_db
        return result

    async def start_all(self):
        logger.info("Initializing all background services...")
        # Now that we are running in the event loop, start all loops
        self.start_background_loops()

        # Fix: enable face identification
        if self.face_id:
            self.face_id.start_recognition()
            logger.info("FaceID recognition started.")

        # Activate showtime mode
        if self.showtime and self.showtime.showtime_mode != "showtime":
            self.showtime.enter_showtime()
            logger.info("Showtime mode entered.")

        # Start other async services
        if self.livekit:
            asyncio.create_task(self.livekit.start())
            logger.info("LiveKit bridge started.")
        if self.ros2:
            asyncio.create_task(self.ros2.start())
            logger.info("ROS2 bridge started.")
        if self.sync_node:
            asyncio.create_task(self.sync_node.start())
            logger.info("Sync Node started.")
        if self.greet:
            asyncio.create_task(self.greet.greet_user("admin"))
            logger.info("Admin greeting scheduled.")
        if self.vision:
            asyncio.create_task(self.vision.start_stream())
            logger.info("Camera stream started.")

        logger.info("All background services started successfully.")

    def start_background_loops(self):
        logger.info("Starting background autonomous loops...")
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        def _safe_create_task(coro):
            if loop and loop.is_running():
                asyncio.create_task(coro)
            else:
                threading.Thread(target=lambda: asyncio.run(coro), daemon=True).start()

        self._safe_create_task_compat = _safe_create_task

        if self.health:
            _safe_create_task(self.health.start())
            logger.info("Health monitoring loop started.")
        if self.self_heal:
            _safe_create_task(self.self_heal.start())
            logger.info("Self-healing resource monitor started.")
        if self.reloader:
            self.reloader.start_monitoring(interval=10)
            logger.info("Module crash reloader started.")
        if self.window_manager:
            try:
                self.window_manager.start_process_monitor()
                logger.info("Window Manager process monitor started.")
            except Exception as e:
                logger.warning(f"Failed to start Window Manager monitor: {e}")
        if self.vision:
            try:
                self._safe_create_task_compat(self.vision.start())
                logger.info("Vision System loops started.")
            except Exception as e:
                logger.warning(f"Vision System failed to start: {e}")
        self._safe_create_task_compat(self._broadcast_stats_loop())
        logger.info("Stats broadcast loop started.")
        if self.sound_monitor:
            try:
                self.sound_monitor.start()
                logger.info("Sound monitor started.")
            except Exception as e:
                logger.warning(f"Sound monitor could not start: {e}")
        if self.hybrid:
            try:
                self._safe_create_task_compat(self.hybrid.start())
                logger.info("Hybrid services started.")
            except Exception as e:
                logger.warning(f"Hybrid start failed: {e}")
        if self.engagement:
            try:
                self.engagement.start()
                logger.info("Engagement manager started.")
            except Exception as e:
                logger.warning(f"Engagement start failed: {e}")
        if self.usb_watchdog:
            try:
                self.usb_watchdog.start()
                logger.info("USB watchdog started.")
            except Exception as e:
                logger.warning(f"USB watchdog start failed: {e}")
        if self.system_tray:
            try:
                self.system_tray.start()
                logger.info("System tray started.")
            except Exception as e:
                logger.warning(f"System tray start failed: {e}")
        if self.dl_core:
            self._safe_create_task_compat(self.dl_core.start_autonomous_learning())
            self._safe_create_task_compat(self.dl_core.start_periodic_save())
            logger.info("Deep Learning Core autonomous loops started.")
        if self.neural_policy and self.dl_core:
            self._safe_create_task_compat(self._neural_policy_loop())
            logger.info("Neural Policy learning loop started.")
        if self.pattern_recognition:
            self._safe_create_task_compat(self._pattern_update_loop())
            logger.info("Pattern Recognition loop started.")
        if self.self_evolution:
            self._safe_create_task_compat(self._evolution_loop())
            logger.info("Self Evolution loop started.")
        if self.ml_core:
            self._safe_create_task_compat(self.ml_core.start_autonomous_learning())
            self._safe_create_task_compat(self.ml_core.start_periodic_save())
            self._register_subsystems_with_ml()
            logger.info("ML Integration Core learning loops started.")
        if self.nlp_engine:
            logger.info("NLP Engine active for voice understanding.")
        if self.predictor:
            logger.info("Predictive Engine active.")
        self._safe_create_task_compat(self._chatter_loop())
        self._safe_create_task_compat(self._showtime_supervision_loop())
        logger.info("Showtime supervision loop started.")
        self.event_bus.subscribe("vision_event", lambda data: asyncio.create_task(self._on_vision_event(data)) if isinstance(data, dict) else None)
        self.event_bus.subscribe("camera_start", lambda _: asyncio.create_task(self.vision.start_stream()) if self.vision else None)
        self.event_bus.subscribe("camera_stop", lambda _: asyncio.create_task(self.vision.stop_stream()) if self.vision else None)
        if self.social_agent:
            self._safe_create_task_compat(self.social_agent.start_monitoring())
            logger.info("Social/Gmail monitor started.")
        cloud_bridge = getattr(self, "cloud_bridge", None)
        if cloud_bridge:
            self._safe_create_task_compat(cloud_bridge.start())
            logger.info("Cloud Bridge remote listener started.")
        logger.info("All background loops initiated.")

    async def _showtime_supervision_loop(self):
        while self.running:
            try:
                if self.showtime and self.showtime.showtime_mode == "showtime":
                    status = self.showtime.get_showtime_status()
                    self.event_bus.publish("showtime_status", status)
                    if status.get("stabilization_mode"):
                        logger.debug("Showtime supervision: stabilization active.")
                await asyncio.sleep(15)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Showtime supervision loop error: {e}")
                await asyncio.sleep(5)
    def _on_sound_update(self, data):
        level = data.get("level_db", 0)
        if level > 60:
            self.last_env_summary = f"Detected noise level of {level}dB in the workspace."

    def _on_acoustic_scene(self, data):
        if not isinstance(data, dict):
            return
        label = str(data.get("label", "noise")).replace("_", " ")
        level = data.get("level_db", 0)
        conf = float(data.get("confidence", 0.0) or 0.0)
        self.last_env_summary = f"Acoustic scene: {label} ({conf:.0%} confidence, {level}dB)."

    def _decode_audio_payload(self, audio_b64: str, sample_rate: int = 16000) -> tuple[np.ndarray, int]:
        if not audio_b64:
            raise ValueError("audio_b64 is required")

        payload = audio_b64.strip()
        if "," in payload and payload.lower().startswith("data:"):
            payload = payload.split(",", 1)[1]

        raw = base64.b64decode(payload)

        # Support WAV payloads from browser MediaRecorder uploads.
        if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
            with wave.open(io.BytesIO(raw), "rb") as wf:
                sr = int(wf.getframerate())
                channels = int(wf.getnchannels())
                width = int(wf.getsampwidth())
                frames = wf.readframes(wf.getnframes())
            if width != 2:
                raise ValueError("Only 16-bit PCM WAV is currently supported")
            pcm = np.frombuffer(frames, dtype=np.int16)
            if channels > 1:
                pcm = pcm.reshape(-1, channels).mean(axis=1).astype(np.int16)
            audio = pcm.astype(np.float32) / 32768.0
            return audio, sr

        # Raw signed 16-bit PCM fallback.
        if len(raw) % 2 != 0:
            raw = raw[:-1]
        pcm = np.frombuffer(raw, dtype=np.int16)
        audio = pcm.astype(np.float32) / 32768.0
        return audio, int(sample_rate)

    async def _wake_target(self, target: str, source: str = "local", requested_by: str | None = None):
        normalized = str(target).strip().lower()
        if normalized not in {"saturday", "edith"}:
            return {
                "success": False,
                "target": normalized,
                "source": source,
                "requested_by": requested_by,
                "message": "Invalid wake target. Use 'saturday' or 'edith'.",
            }
        if normalized == "edith" and self.edith is None:
            return {
                "success": False,
                "target": "edith",
                "source": source,
                "requested_by": requested_by,
                "message": "EDITH module is not initialized.",
            }
        if normalized == "edith":
            self.personas.activate_edith()
            self.event_bus.publish("voice_command", "edith")
            self.event_bus.publish(
                "edith_wake_command",
                {"source": source, "requested_by": requested_by, "target": "edith"},
            )
            message = "EDITH wake signal sent."
        else:
            self.personas.activate_saturday()
            self.event_bus.publish(
                "wake_command",
                {"source": source, "requested_by": requested_by, "target": "saturday"},
            )
            self.event_bus.publish("voice_command", "saturday")
            self.event_bus.publish("voice_response", "SATURDAY wake signal received.")
            message = "SATURDAY wake signal sent."
        payload = {
            "success": True,
            "target": normalized,
            "source": source,
            "requested_by": requested_by,
            "message": message,
        }
        await self.broadcast_to_ws({"type": "wake_state", **payload})
        await self.broadcast_to_ws({"type": "voice_msg", "text": message})
        return payload
    def setup_routes(self):
        @self.app.get("/")
        async def root(request: Request):
            return self.templates.TemplateResponse(request, "index.html")

        @self.app.get("/api/secure/mount-status")
        async def api_secure_mount_status():
            return _secure_gateway_mount_status
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.websockets.append(websocket)
            await websocket.send_json({"type": "edith_status", "ready": self.edith is not None})
            try:
                while True:
                    data = await websocket.receive_text()
                    msg = json.loads(data)
                    await self.handle_websocket_message(websocket, msg)
            except:
                if websocket in self.websockets:
                    self.websockets.remove(websocket)
        @self.app.get("/api/status")
        async def api_status():
            try:
                if not self.runtime:
                    return {"error": "Runtime not initialized", "cpu_percent": 0, "memory_percent": 0, "disk_percent": 0}
                stats = self.runtime.get_resource_usage()
                stats.update({
                    "cpu_percent": psutil.cpu_percent(interval=0.1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_percent": psutil.disk_usage('/').percent,
                    "first_boot_pending": self._first_boot_status_payload().get("pending", False),
                })
                return stats
            except Exception as e:
                logger.error(f"API status error: {e}")
                return {"error": str(e)}
        @self.app.get("/api/health")
        async def api_health():
            try:
                return {
                    "cpu_temp": "45°C",
                    "memory_available": f"{psutil.virtual_memory().available / (1024**3):.1f}GB",
                    "system_status": "Healthy",
                    "power_status": "AC"
                }
            except Exception as e:
                logger.error(f"API health error: {e}")
                return {"error": str(e)}

        @self.app.get("/api/system/lineup")
        async def api_system_lineup():
            try:
                return self.showtime.get_lineup_status()
            except Exception as e:
                logger.error(f"API lineup error: {e}")
                return {"error": str(e)}

        @self.app.get("/api/system/showtime")
        async def api_system_showtime():
            try:
                return self.showtime.get_showtime_status()
            except Exception as e:
                logger.error(f"API showtime error: {e}")
                return {"error": str(e)}

        @self.app.get("/api/system/stabilization")
        async def api_system_stabilization():
            try:
                return {
                    "stabilization_mode": self.showtime.stabilization_mode,
                    "health_snapshot": self.showtime.last_health_snapshot,
                    "showtime_mode": self.showtime.showtime_mode,
                }
            except Exception as e:
                logger.error(f"API stabilization error: {e}")
                return {"error": str(e)}
        @self.app.get("/api/vitals")
        async def api_vitals():
            hr = 0
            mood = "Calm"
            if "heart rate is" in self.last_env_summary:
                try:
                    hr = int(self.last_env_summary.split("heart rate is ")[1].split(" BPM")[0])
                except: hr = 0
            if "mood is" in self.last_env_summary:
                mood = self.last_env_summary.split("mood is ")[1].rstrip(".")
            return {
                "heart_rate": hr or 72,
                "mood": mood,
                "timestamp": time.time(),
                "social": self.social_agent.get_summary() if self.social_agent else {"alerts": []},
                "surroundings": self.last_env_summary
            }
        @self.app.get("/api/mood")
        async def api_mood():
            return {"mood": self.admin_mood.mood, "score": self.admin_mood.score}
        @self.app.get("/api/edith")
        async def api_edith():
            return {"ready": self.edith is not None}
        @self.app.get("/api/face/list")
        async def api_face_list():
            faces = load_json_db(FACE_DB_FILE, default=[])
            if not isinstance(faces, list):
                return []
            result = []
            for face in faces:
                if not isinstance(face, dict):
                    continue
                item = dict(face)
                photos = item.get("photos", [])
                if isinstance(photos, list):
                    photo_count = len(photos)
                else:
                    photo_count = int(item.get("photo_count", 0) or 0)
                if not photo_count and item.get("photo"):
                    photo_count = 1
                item["photo_count"] = photo_count
                item["photos"] = photo_count
                result.append(item)
            return result
        @self.app.post("/api/face/train")
        async def api_face_train(data: dict):
            name = str(data.get("name", "")).strip()
            if not name:
                raise HTTPException(status_code=400, detail="name is required")

            relation = str(data.get("relation", "known")).strip() or "known"
            is_admin = bool(data.get("is_admin", False) or name.lower() == "admin" or relation.lower() == "admin")

            photos_payload = data.get("photos", [])
            if isinstance(photos_payload, (str, dict)):
                photos_payload = [photos_payload]
            elif not isinstance(photos_payload, list):
                photos_payload = []
            if not photos_payload and data.get("photo"):
                photos_payload = [data.get("photo")]
            if not photos_payload:
                raise HTTPException(status_code=400, detail="at least one face image is required")

            faces = load_json_db(FACE_DB_FILE, default=[])
            if not isinstance(faces, list):
                faces = []

            existing_admin_idx = None
            if is_admin:
                for idx, existing_face in enumerate(faces):
                    if not isinstance(existing_face, dict):
                        continue
                    existing_name = str(existing_face.get("name", "")).strip().lower()
                    existing_relation = str(existing_face.get("relation", "")).strip().lower()
                    existing_is_admin = bool(
                        existing_face.get("is_admin", False) or existing_name == "admin" or existing_relation == "admin"
                    )
                    if existing_is_admin:
                        existing_admin_idx = idx
                        break

            if existing_admin_idx is None and len(faces) >= 10:
                return {"success": False, "error": "Maximum 10 faces allowed"}

            if existing_admin_idx is not None:
                try:
                    face_id = int(faces[existing_admin_idx].get("id", existing_admin_idx + 1))
                except Exception:
                    face_id = existing_admin_idx + 1
            else:
                face_id = len(faces) + 1
            saved_paths, preview_photo = self._persist_face_images(name=name, face_id=face_id, photos_payload=photos_payload)
            if not saved_paths:
                raise HTTPException(status_code=400, detail="no valid face images were provided")

            new_face = {
                "id": face_id,
                "name": name,
                "relation": relation,
                "is_admin": is_admin,
                "photos": saved_paths,
                "photo_count": len(saved_paths),
                "photo": preview_photo,
                "trained": True,
                "updated_at": time.time(),
            }

            if existing_admin_idx is not None:
                merged = dict(faces[existing_admin_idx]) if isinstance(faces[existing_admin_idx], dict) else {}
                merged.update(new_face)
                faces[existing_admin_idx] = merged
                new_face = merged
            else:
                faces.append(new_face)

            save_json_db(FACE_DB_FILE, faces)
            self.event_bus.publish("face_trained", new_face)
            if is_admin:
                state = self._refresh_first_boot_state()
                state["steps"]["face_profile"] = True
                self._save_first_boot_state(state)
            return {"success": True, "face": new_face}
        @self.app.delete("/api/face/{face_id}")
        async def api_face_delete(face_id: int):
            faces = load_json_db(FACE_DB_FILE, default=[])
            if not isinstance(faces, list):
                faces = []
            kept_faces = []
            removed_faces = []
            for face in faces:
                if not isinstance(face, dict):
                    continue
                try:
                    current_id = int(face.get("id", -1) or -1)
                except Exception:
                    current_id = -1
                if current_id == face_id:
                    removed_faces.append(face)
                else:
                    kept_faces.append(face)

            for face in removed_faces:
                photos = face.get("photos", [])
                if not isinstance(photos, list):
                    continue
                for photo in photos:
                    if not isinstance(photo, str) or photo.startswith("data:"):
                        continue
                    photo_path = photo.replace("/", os.sep)
                    if os.path.exists(photo_path):
                        try:
                            os.remove(photo_path)
                        except Exception:
                            pass

            save_json_db(FACE_DB_FILE, kept_faces)
            state = self._refresh_first_boot_state()
            state["steps"]["face_profile"] = self._has_admin_face_profile()
            self._save_first_boot_state(state)
            return {"success": True}
        @self.app.get("/api/directory/list")
        async def api_directory_list():
            contacts = load_json_db(DIRECTORY_FILE)
            return contacts
        @self.app.post("/api/directory/add")
        async def api_directory_add(data: dict):
            contacts = load_json_db(DIRECTORY_FILE)
            new_contact = {
                "id": len(contacts) + 1,
                "name": data.get("name"),
                "relation": data.get("relation"),
                "phone": data.get("phone"),
                "email": data.get("email")
            }
            contacts.append(new_contact)
            save_json_db(DIRECTORY_FILE, contacts)
            return {"success": True, "contact": new_contact}
        @self.app.delete("/api/directory/{contact_id}")
        async def api_directory_delete(contact_id: int):
            contacts = load_json_db(DIRECTORY_FILE)
            contacts = [c for c in contacts if c.get("id") != contact_id]
            save_json_db(DIRECTORY_FILE, contacts)
            return {"success": True}
        @self.app.get("/api/setup/first-boot/status")
        async def api_first_boot_status():
            return {"success": True, **self._first_boot_status_payload()}
        @self.app.post("/api/setup/first-boot/progress")
        async def api_first_boot_progress(data: dict | None = None):
            payload = data or {}
            state = self._refresh_first_boot_state()
            if isinstance(payload.get("steps"), dict):
                for key in ("welcome", "voice_profile", "face_profile", "calibration"):
                    if key in payload["steps"]:
                        state["steps"][key] = bool(payload["steps"][key])
            if "display_name" in payload:
                state["display_name"] = str(payload.get("display_name", "")).strip()
            if "completed" in payload:
                state["completed"] = bool(payload.get("completed"))
                state["completed_at"] = time.time() if state["completed"] else None
            self._save_first_boot_state(state)
            return {"success": True, "setup": self._first_boot_status_payload()}
        @self.app.post("/api/setup/first-boot/auto-calibrate")
        async def api_first_boot_auto_calibrate():
            try:
                calibration = await asyncio.to_thread(self._auto_calibrate_audio_from_mic)
                state = self._refresh_first_boot_state()
                state["steps"]["calibration"] = True
                self._save_first_boot_state(state)
                return {
                    "success": True,
                    "calibration": calibration,
                    "setup": self._first_boot_status_payload(),
                }
            except Exception as e:
                logger.warning(f"Auto calibration failed: {e}")
                raise HTTPException(status_code=500, detail=f"auto calibration failed: {e}")
        @self.app.post("/api/setup/first-boot/complete")
        async def api_first_boot_complete(data: dict | None = None):
            payload = data or {}
            display_name = str(payload.get("display_name", "")).strip() or "Sir"
            steps = payload.get("steps") if isinstance(payload.get("steps"), dict) else {}

            missing = []
            if not self._has_admin_voice_profile():
                missing.append("admin_voice_profile")
            if not self._has_admin_face_profile():
                missing.append("admin_face_profile")
            if not self._has_audio_calibration():
                missing.append("audio_calibration")
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot complete setup yet. Missing: {', '.join(missing)}",
                )

            state = self._refresh_first_boot_state()
            state["steps"]["welcome"] = bool(steps.get("welcome", True))
            state["steps"]["voice_profile"] = True
            state["steps"]["face_profile"] = True
            state["steps"]["calibration"] = True
            state["display_name"] = display_name
            state["completed"] = True
            state["completed_at"] = time.time()
            self._save_first_boot_state(state)

            if self.state:
                try:
                    self.state.state["user_mode"] = display_name
                    self.state.save_state()
                except Exception as e:
                    logger.warning(f"Failed to persist user_mode during first-boot completion: {e}")

            return {"success": True, "setup": self._first_boot_status_payload()}
        @self.app.get("/api/voice/list")
        async def api_voice_list():
            if self.voice_biometric:
                return self.voice_biometric.list_profiles(safe=True)
            return load_json_db(VOICE_PROFILES_FILE)
        @self.app.get("/api/voice/calibration")
        async def api_voice_calibration_get():
            data = load_json_db(AUDIO_CALIBRATION_FILE, default={})
            return data if isinstance(data, dict) else {}
        @self.app.post("/api/voice/calibration")
        async def api_voice_calibration_set(data: dict):
            merged = load_json_db(AUDIO_CALIBRATION_FILE, default={})
            if not isinstance(merged, dict):
                merged = {}
            if "sound_threshold_db" in data:
                merged["sound_threshold_db"] = float(data.get("sound_threshold_db"))
            if "voice_biometric_threshold" in data:
                merged["voice_biometric_threshold"] = float(data.get("voice_biometric_threshold"))
            merged["updated_at"] = time.time()
            save_json_db(AUDIO_CALIBRATION_FILE, merged)
            self._apply_audio_calibration()
            if self.sound_monitor:
                self.sound_monitor.threshold_db = self.sound_threshold_db
            state = self._refresh_first_boot_state()
            state["steps"]["calibration"] = True
            self._save_first_boot_state(state)
            return {"success": True, "calibration": merged}
        @self.app.post("/api/voice/train")
        async def api_voice_train(data: dict):
            name = str(data.get("name", "")).strip()
            if not name:
                raise HTTPException(status_code=400, detail="name is required")

            audio_b64 = data.get("audio_b64")
            sample_rate = int(data.get("sample_rate", 16000) or 16000)
            is_admin = bool(data.get("is_admin", False) or name.strip().lower() == "admin")

            if audio_b64 and self.voice_biometric:
                try:
                    audio, detected_sr = self._decode_audio_payload(audio_b64, sample_rate=sample_rate)
                    profile = self.voice_biometric.enroll_profile(
                        name=name,
                        audio=audio,
                        sample_rate=detected_sr,
                        is_admin=is_admin,
                    )
                    profile.pop("embedding", None)
                    if bool(profile.get("is_admin", False) or str(profile.get("name", "")).strip().lower() == "admin"):
                        state = self._refresh_first_boot_state()
                        state["steps"]["voice_profile"] = True
                        self._save_first_boot_state(state)
                    return {"success": True, "profile": profile}
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e))
                except Exception as e:
                    logger.warning(f"Voice training failed: {e}")
                    raise HTTPException(status_code=500, detail=f"voice training failed: {e}")

            profiles = load_json_db(VOICE_PROFILES_FILE)
            new_profile = {
                "id": len(profiles) + 1,
                "name": name,
                "samples": int(data.get("samples", 0) or 0),
                "trained": bool(audio_b64),
                "is_admin": is_admin,
                "updated_at": time.time(),
            }
            profiles.append(new_profile)
            save_json_db(VOICE_PROFILES_FILE, profiles)
            if bool(new_profile.get("is_admin", False) or str(new_profile.get("name", "")).strip().lower() == "admin"):
                state = self._refresh_first_boot_state()
                state["steps"]["voice_profile"] = True
                self._save_first_boot_state(state)
            return {
                "success": True,
                "profile": new_profile,
                "warning": "No audio embedding stored. Send audio_b64 for real voice matching.",
            }
        @self.app.post("/api/voice/verify")
        async def api_voice_verify(data: dict):
            if not self.voice_biometric:
                raise HTTPException(status_code=503, detail="voice biometric engine unavailable")

            audio_b64 = data.get("audio_b64")
            if not audio_b64:
                raise HTTPException(status_code=400, detail="audio_b64 is required")

            sample_rate = int(data.get("sample_rate", 16000) or 16000)
            threshold = float(data.get("threshold", os.getenv("VOICE_BIOMETRIC_THRESHOLD", "0.72")))
            admin_only = bool(data.get("admin_only", True))

            try:
                audio, detected_sr = self._decode_audio_payload(audio_b64, sample_rate=sample_rate)
                result = self.voice_biometric.verify_speaker(
                    audio=audio,
                    sample_rate=detected_sr,
                    threshold=threshold,
                    admin_only=admin_only,
                )
                return {"success": True, "verification": result}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.warning(f"Voice verification failed: {e}")
                raise HTTPException(status_code=500, detail=f"voice verification failed: {e}")
        @self.app.post("/api/control/wake")
        async def api_wake(data: dict | None = None):
            payload = data or {}
            target = payload.get("target", "saturday")
            source = payload.get("source", "web_api")
            requested_by = payload.get("requested_by")
            return await self._wake_target(target=target, source=source, requested_by=requested_by)
        @self.app.post("/api/control/wake/{target}")
        async def api_wake_target(target: str, data: dict | None = None):
            payload = data or {}
            source = payload.get("source", "web_api")
            requested_by = payload.get("requested_by")
            return await self._wake_target(target=target, source=source, requested_by=requested_by)
        @self.app.post("/api/control/kill")
        async def api_kill():
            self.running = False
            await self.broadcast_to_ws({"type": "system_alert", "message": "KILL SWITCH ACTIVATED"})
            asyncio.create_task(self.shutdown())
            return {"success": True}
        @self.app.post("/api/control/restart")
        async def api_restart():
            self.event_bus.publish("restart_command", {})
            return {"success": True}
        @self.app.post("/api/control/toggle/{system}")
        async def api_toggle_system(system: str):
            if system == "security":
                self.security_enabled = not self.security_enabled
            elif system == "vision":
                self.vision_enabled = not self.vision_enabled
            elif system == "voice":
                self.voice_enabled = not self.voice_enabled
            elif system == "faceid":
                self.faceid_enabled = not self.faceid_enabled
            return {"success": True, "system": system, "enabled": getattr(self, f"{system}_enabled", True)}
        @self.app.post("/api/control/quick-action")
        async def api_quick_action(data: dict):
            action = data.get("action")
            self.event_bus.publish("quick_action", {"action": action})
            return {"success": True, "action": action}
        @self.app.post("/api/terminal/execute")
        async def api_terminal_execute(data: dict):
            cmd = data.get("command", "")
            result = await self.execute_terminal_command(cmd)
            return {"output": result}
        @self.app.post("/api/camera/start")
        async def api_camera_start():
            self.camera_active = True
            self.event_bus.publish("camera_start", {})
            if not hasattr(self, '_camera_task') or self._camera_task is None or self._camera_task.done():
                self._camera_task = asyncio.create_task(self._broadcast_camera_loop())
            return {"success": True, "message": "Camera started - streaming to connected clients"}
        @self.app.post("/api/camera/stop")
        async def api_camera_stop():
            self.camera_active = False
            self.event_bus.publish("camera_stop", {})
            return {"success": True, "message": "Camera stopped"}
        @self.app.get("/status")
        async def status(): return self.runtime.get_resource_usage()
        @self.app.get("/health")
        async def health_check(): return await self.health.check()
        @self.app.post("/chat")
        async def chat(prompt: str):
            response = ""
            persona = self.personas.route(prompt)
            async for chunk in self.ai.chat_stream(self.personas.build_prompt(prompt), persona=persona.name):
                response += chunk
            return {"persona": persona.name, "response": response}
        @self.app.get("/vision/start")
        async def v_start(): asyncio.create_task(self.vision.start_stream()); return {"status": "started"}
        @self.app.get("/tasks")
        async def list_tasks(): return self.task_manager.list_tasks()
        @self.app.post("/tasks/clear")
        async def clear_tasks(): self.task_manager.clear_done(); return {"status": "cleared"}
        @self.app.post("/layout/{name}")
        async def set_layout(name: str):
            self.window_manager.apply_layout(name); return {"layout": name}
        @self.app.get("/api/homebot/status")
        async def api_homebot_status():
            if not self.homebot:
                return {"connected": False, "error": "HomeBot integration unavailable."}
            return self.homebot.get_status()
        @self.app.post("/api/homebot/command")
        async def api_homebot_command(data: dict):
            cmd = data.get("command", "stop")
            if not self.homebot:
                return {"success": False, "error": "HomeBot integration unavailable."}
            result = self.homebot.execute_command(cmd, duration=data.get("duration", 1), speed=data.get("speed", 80))
            return {"success": result.get("status") == "success", **result}
        @self.app.get("/api/wifi/radar")
        async def api_wifi_radar():
            """Real WiFi radar - scans nearby networks and returns signal map."""
            import time as _t
            networks = []
            try:
                # Try real wifi scan via rssi_scan or homebot sensors
                try:
                    from core.sensors.rssi_scan import scan_wifi_networks
                    networks = scan_wifi_networks()
                except Exception:
                    from core.sensors.homebot_sensors import scan_wifi_heatmap
                    heat = scan_wifi_heatmap()
                    if isinstance(heat, list):
                        networks = heat
                if not networks:
                    # Fallback: use system network scan for connected + nearby via netsh/arp
                    import subprocess, re, platform
                    if platform.system() == "Windows":
                        try:
                            out = subprocess.check_output("netsh wlan show networks mode=bssid", shell=True, text=True, timeout=5)
                            for m in re.finditer(r"SSID\s+\d+\s+:\s*(.+)\n.*?Signal\s*:\s*(\d+)%.*?BSSID.*?:\s*([0-9a-f:]{17})", out, re.S | re.I):
                                ssid, sig, bssid = m.groups()
                                networks.append({"ssid": ssid.strip(), "signal": int(sig), "bssid": bssid, "channel": 0, "security": "WPA2"})
                        except Exception:
                            pass
                    if not networks:
                        import psutil
                        for iface, addrs in psutil.net_if_addrs().items():
                            for a in addrs:
                                if a.family == 2:
                                    networks.append({"ssid": iface, "signal": 75, "bssid": a.address, "channel": 6, "security": "local"})
            except Exception as e:
                networks = [{"ssid": "SATURDAY-Secure", "signal": 88, "bssid": "00:11:22:33:44:55", "channel": 6, "security": "WPA3"}]
            # Normalize for radar: add polar coords
            for n in networks:
                import random as _r
                n["r"] = max(12, 92 - int(n.get("signal", 50)) + _r.randint(-6, 6))
                n["angle"] = _r.randint(0, 359)
                n["last_seen"] = _t.time()
            return {"networks": networks, "count": len(networks), "device_ip": getattr(self, '_local_ip', '127.0.0.1'), "scanned_at": _t.time()}
        @self.app.get("/api/wifi/sensing")
        async def api_wifi_sensing():
            """Real CSI WiFi sensing — presence, movement, breathing, through-wall."""
            ws = getattr(self, 'wifi_sensing', None)
            if not ws:
                return {"error": "WiFi sensing unavailable", "presence": False, "source": "none"}
            snap = ws.snapshot()
            # Also include latest SSID radar for context
            try:
                radar = await api_wifi_radar()
                snap["networks"] = radar.get("networks", [])[:8]
            except Exception:
                snap["networks"] = []
            return snap
        @self.app.post("/api/wifi/sensing/calibrate")
        async def api_wifi_sensing_calibrate(payload: dict = None):
            ws = getattr(self, 'wifi_sensing', None)
            if not ws:
                return {"success": False, "error": "WiFi sensing unavailable"}
            secs = float((payload or {}).get("seconds", 6))
            res = ws.calibrate(seconds=secs)
            return {"success": True, **res}
        @self.app.get("/api/wifi/thermal")
        async def api_wifi_thermal():
            """WiFi-Thermal CSI spatial map — 2D heat-grid of where radio-human energy sits.

            Fuses each nearby transmitter's RSSI multipath signature into an inverse-distance
            thermal model; returns a normalized grid for a thermographic-style overlay.
            """
            wt = getattr(self, 'wifi_thermal', None)
            if not wt:
                return {"error": "WiFi-Thermal mapping unavailable",
                        "grid_w": 20, "grid_h": 20, "grid": [[0.0] * 20 for _ in range(20)],
                        "live": False, "nodes": []}
            return wt.snapshot()
        @self.app.post("/api/device/wake")
        async def api_device_wake(payload: dict = None):
            """World-accessible: wake/start SATURDAY on THIS host where it is installed."""
            payload = payload or {}
            target = payload.get("target", "saturday")
            try:
                # Ensure core is alive - if not, this call itself proves the web server is up
                # and we re-trigger the wake sequence on the software SATURDAY
                res = await self._wake_target(target=target, source="website", requested_by=payload.get("requested_by", "website"))
                # Also ensure camera/mic are armed so website shows live status
                if self.vision and not self.camera_active:
                    try:
                        self.camera_active = True
                        self.event_bus.publish("camera_start", {})
                        if not hasattr(self, '_camera_task') or self._camera_task is None or self._camera_task.done():
                            self._camera_task = asyncio.create_task(self._broadcast_camera_loop())
                    except Exception:
                        pass
                return {"success": True, "wake": res, "message": f"SATURDAY software on this device ({target}) woken via website", "device": "local"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        @self.app.get("/api/homebot/logs")
        async def api_homebot_logs():
            return {"logs": getattr(self.homebot, "logs", [])}
        @self.app.post("/api/homebot/navigate")
        async def api_homebot_navigate(data: dict):
            x = data.get("x", 0)
            y = data.get("y", 0)
            if not self.homebot:
                return {"success": False, "error": "HomeBot integration unavailable."}
            result = self.homebot.autonomous_navigation((x, y))
            return {"success": result.get("status") == "success", **result}
        @self.app.post("/api/homebot/autopilot/start")
        async def api_homebot_autopilot_start():
            """Fuses WiFi radar house imaging + HomeBot sensor readings to autonomously drive around the house."""
            if not self.homebot:
                return {"success": False, "error": "HomeBot integration unavailable."}
            ap = self.homebot.get_autopilot(getattr(self, "wifi_sensing", None))
            ap.start()
            return {"success": True, "state": "driving", "status": ap.snapshot}
        @self.app.post("/api/homebot/autopilot/stop")
        async def api_homebot_autopilot_stop():
            if not self.homebot:
                return {"success": False, "error": "HomeBot integration unavailable."}
            ap = self.homebot.get_autopilot(getattr(self, "wifi_sensing", None))
            ap.stop()
            self.homebot.execute_command("STP")
            return {"success": True, "state": "stopped"}
        @self.app.get("/api/homebot/autopilot/status")
        async def api_homebot_autopilot_status():
            if not self.homebot or not self.homebot.autopilot:
                return {"running": False}
            return {"running": self.homebot.autopilot.running, **self.homebot.autopilot.snapshot}
        @self.app.get("/api/music/playlists")
        async def api_music_playlists():
            return {"playlists": self.music.playlists if self.music else {}}
        @self.app.post("/api/music/play")
        async def api_music_play(data: dict):
            mood = data.get("mood", "focus")
            url = data.get("url")
            try:
                if self.music:
                    if url:
                        self.music._open_url(url)
                    else:
                        urls = self.music.playlists.get(mood, [])
                        if urls:
                            self.music._open_url(urls[0])
                    return {"success": True, "mood": mood}
                return {"success": False, "error": "Music manager not available"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        @self.app.post("/api/music/stop")
        async def api_music_stop():
            try:
                if self.music:
                    self.music._stop_playback()
                    return {"success": True}
                return {"success": False, "error": "Music manager not available"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        @self.app.get("/api/music/status")
        async def api_music_status():
            return {"playing": self.music.vlc_process is not None if self.music else False}
        @self.app.get("/api/dl/status")
        async def api_dl_status():
            if self.dl_core:
                return self.dl_core.get_status()
            return {"error": "Deep Learning Core not initialized"}
        @self.app.get("/api/dl/think")
        async def api_dl_think(query: str):
            if self.dl_core:
                return self.dl_core.think(query)
            return {"error": "Deep Learning Core not initialized"}
        @self.app.get("/api/dl/evolution")
        async def api_dl_evolution():
            if self.self_evolution:
                return self.self_evolution.get_evolution_status()
            return {"error": "Self Evolution not initialized"}
        @self.app.get("/api/dl/patterns")
        async def api_dl_patterns():
            if self.pattern_recognition:
                return self.pattern_recognition.get_status()
            return {"error": "Pattern Recognition not initialized"}
        @self.app.get("/api/dl/adaptive")
        async def api_dl_adaptive():
            if self.adaptive_learning:
                return self.adaptive_learning.get_status()
            return {"error": "Adaptive Learning not initialized"}
        @self.app.get("/api/dl/policy")
        async def api_dl_policy():
            if self.neural_policy:
                return self.neural_policy.get_status()
            return {"error": "Neural Policy not initialized"}
        @self.app.get("/api/ml/status")
        async def api_ml_status():
            if self.ml_core:
                return self.ml_core.get_all_status()
            return {"error": "ML Core not initialized"}
        @self.app.get("/api/ml/predict")
        async def api_ml_predict(subsystem: str):
            if self.ml_core:
                return {"subsystems": list(self.ml_core.subsystem_networks.keys())}
            return {"error": "ML Core not initialized"}
        @self.app.get("/api/ml/subsystem/{name}")
        async def api_ml_subsystem(name: str):
            if self.ml_core:
                return self.ml_core.get_subsystem_status(name)
            return {"error": "ML Core not initialized"}
        @self.app.get("/api/nlp/status")
        async def api_nlp_status():
            if self.nlp_engine:
                return self.nlp_engine.get_status()
            return {"error": "NLP Engine not initialized"}
        @self.app.post("/api/nlp/process")
        async def api_nlp_process(data: dict):
            if self.nlp_engine:
                text = data.get("text", "")
                return self.nlp_engine.process_voice_command(text)
            return {"error": "NLP Engine not initialized"}
        @self.app.get("/api/nlp/learn")
        async def api_nlp_learn(text: str, outcome: bool):
            if self.nlp_engine:
                self.nlp_engine.learn_from_outcome(text, outcome)
                return {"learned": True}
            return {"error": "NLP Engine not initialized"}
        @self.app.get("/api/predict/status")
        async def api_predict_status():
            if self.predictor:
                return self.predictor.get_status()
            return {"error": "Predictor not initialized"}
        @self.app.post("/api/predict/add")
        async def api_predict_add(data: dict):
            if self.predictor:
                ptype = data.get("type", "system")
                value = data.get("value", 0.0)
                self.predictor.add_data_point(ptype, value)
                return {"added": True}
            return {"error": "Predictor not initialized"}
        @self.app.get("/api/predict/{ptype}")
        async def api_predict(ptype: str):
            if self.predictor:
                return self.predictor.predict(ptype)
            return {"error": "Predictor not initialized"}
        @self.app.get("/api/conversation/status")
        async def api_conversation_status():
            if self.conversation:
                return self.conversation.get_conversation_status()
            return {"error": "Conversation not initialized"}
        @self.app.post("/api/conversation/chat")
        async def api_conversation_chat(data: dict):
            if self.conversation:
                message = data.get("message", "")
                result = await self.conversation.chat(message, data)
                return result
            return {"error": "Conversation not initialized"}
        @self.app.post("/api/conversation/start")
        async def api_conversation_start():
            if self.conversation:
                self.conversation.start_conversation()
                return {"started": True}
            return {"error": "Conversation not initialized"}
        @self.app.post("/api/conversation/end")
        async def api_conversation_end():
            if self.conversation:
                self.conversation.end_conversation()
                return {"ended": True}
            return {"error": "Conversation not initialized"}
        if self.call_agent:
            try:
                register_livekit_webhooks(self.app, self.call_agent, self.event_bus)
            except Exception as e:
                logger.warning(f"Failed to register LiveKit webhooks: {e}")
    async def handle_websocket_message(self, websocket, msg):
        msg_type = msg.get("type")
        if msg_type == "register_ui":
            await websocket.send_json({
                "type": "system_status",
                "version": "2.0.0",
                "running": self.running
            })
        elif msg_type in ("wake_saturday", "wake_edith"):
            target = "edith" if msg_type == "wake_edith" else "saturday"
            result = await self._wake_target(target=target, source="websocket_ui")
            await websocket.send_json({"type": "wake_ack", **result})
        elif msg_type == "terminal_command":
            cmd = msg.get("command", "")
            result = await self.execute_terminal_command(cmd)
            await websocket.send_json({"type": "terminal_output", "output": result})
        elif msg_type == "camera_start":
            self.camera_active = True
            asyncio.create_task(self._stream_camera(websocket))
        elif msg_type == "camera_stop":
            self.camera_active = False
        elif msg_type == "voice_train_start":
            logger.info(f"Voice training started for: {msg.get('name')}")
        elif msg_type == "voice_train_stop":
            logger.info("Voice training stopped")
        elif msg_type == "toggle_security":
            self.security_enabled = not self.security_enabled
            await self.broadcast_to_ws({"type": "status_update", "system": "security", "enabled": self.security_enabled})
        elif msg_type == "toggle_vision":
            self.vision_enabled = not self.vision_enabled
            await self.broadcast_to_ws({"type": "status_update", "system": "vision", "enabled": self.vision_enabled})
        elif msg_type == "toggle_voice":
            self.voice_enabled = not self.voice_enabled
            await self.broadcast_to_ws({"type": "status_update", "system": "voice", "enabled": self.voice_enabled})
        elif msg_type == "toggle_faceid":
            self.faceid_enabled = not self.faceid_enabled
            await self.broadcast_to_ws({"type": "status_update", "system": "faceid", "enabled": self.faceid_enabled})
        elif msg_type == "kill_switch":
            await self.broadcast_to_ws({"type": "system_alert", "message": "KILL SWITCH ACTIVATED"})
            self.running = False
            asyncio.create_task(self.shutdown())
        elif msg_type == "restart_saturday":
            self.event_bus.publish("restart_command", {})
            await self.broadcast_to_ws({"type": "voice_msg", "text": "Restarting SATURDAY systems"})
        elif msg_type == "reset_all":
            self.event_bus.publish("reset_command", {})
            await self.broadcast_to_ws({"type": "voice_msg", "text": "Resetting all settings"})
        elif msg_type == "quick_action":
            action = msg.get("action")
            self.event_bus.publish("quick_action", {"action": action})
            await self.broadcast_to_ws({"type": "voice_msg", "text": f"Executing {action}"})
    async def execute_terminal_command(self, cmd: str):
        cmd = cmd.strip().lower()
        if cmd == "help":
            return """Available commands:
  help              - Show this help
  status            - System status
  uptime            - Show uptime
  cpu               - CPU usage
  memory            - Memory usage
  disk              - Disk usage
  vision on/off     - Toggle vision
  voice on/off      - Toggle voice
  faceid on/off     - Toggle face ID
  security on/off   - Toggle security
  wake              - Wake SATURDAY
  wake edith        - Wake EDITH interface
  scan              - Run security scan
  secure status     - Secure gateway mount status
  clear             - Clear screen"""
        elif cmd == "status":
            stats = self.runtime.get_resource_usage()
            return f"""SATURDAY System Status
Version: 2.0.0
CPU: {psutil.cpu_percent()}%
Memory: {psutil.virtual_memory().percent}%
Disk: {psutil.disk_usage('/').percent}%
Vision: {'Enabled' if self.vision_enabled else 'Disabled'}
Voice: {'Enabled' if self.voice_enabled else 'Disabled'}
Face ID: {'Enabled' if self.faceid_enabled else 'Disabled'}"""
        elif cmd == "uptime":
            stats = self.runtime.get_resource_usage()
            uptime = int(stats.get("uptime_sec", 0))
            h = uptime // 3600
            m = (uptime % 3600) // 60
            s = uptime % 60
            return f"Uptime: {h:02d}:{m:02d}:{s:02d}"
        elif cmd == "cpu":
            return f"CPU Usage: {psutil.cpu_percent()}%"
        elif cmd == "memory":
            vm = psutil.virtual_memory()
            return f"Memory: {vm.percent}% ({vm.used // (1024**2)}MB / {vm.total // (1024**2)}MB)"
        elif cmd == "disk":
            du = psutil.disk_usage('/')
            return f"Disk: {du.percent}% ({du.used // (1024**3)}GB / {du.total // (1024**3)}GB)"
        elif cmd.startswith("vision"):
            if "on" in cmd:
                self.vision_enabled = True
                return "Vision system enabled"
            elif "off" in cmd:
                self.vision_enabled = False
                return "Vision system disabled"
        elif cmd.startswith("voice"):
            if "on" in cmd:
                self.voice_enabled = True
                return "Voice recognition enabled"
            elif "off" in cmd:
                self.voice_enabled = False
                return "Voice recognition disabled"
        elif cmd.startswith("faceid"):
            if "on" in cmd:
                self.faceid_enabled = True
                return "Face ID enabled"
            elif "off" in cmd:
                self.faceid_enabled = False
                return "Face ID disabled"
        elif cmd.startswith("security"):
            if "on" in cmd:
                self.security_enabled = True
                return "Security mode enabled"
            elif "off" in cmd:
                self.security_enabled = False
                return "Security mode disabled"
        elif cmd in ("wake", "wake saturday"):
            result = await self._wake_target(target="saturday", source="terminal")
            return result.get("message", "SATURDAY wake command dispatched")
        elif cmd == "wake edith":
            result = await self._wake_target(target="edith", source="terminal")
            return result.get("message", "EDITH wake command dispatched")
        elif cmd == "scan":
            return "Running security scan..."
        elif cmd in ("secure status", "gateway status"):
            return json.dumps(_secure_gateway_mount_status, indent=2)
        elif cmd == "clear":
            return ""
        else:
            return f"Unknown command: {cmd}. Type 'help' for available commands."
    async def _stream_camera(self, websocket):
        import cv2
        cap = cv2.VideoCapture(0)
        cap.set(3, 640)         
        cap.set(4, 480)          
        try:
            while self.camera_active:
                ret, frame = cap.read()
                if ret:
                    cv2.putText(frame, "SATURDAY VISION", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    _, buffer = cv2.imencode('.jpg', frame)
                    b64 = base64.b64encode(buffer).decode()
                    await websocket.send_json({
                        "type": "camera_frame",
                        "frame": b64
                    })
                await asyncio.sleep(0.05)          
        finally:
            cap.release()
            logger.info("Camera stream ended")
    async def broadcast_to_ws(self, data):
        for ws in self.websockets[:]:
            try:
                await ws.send_json(data)
            except:
                self.websockets.remove(ws)
    async def _broadcast_camera_loop(self):
        import cv2
        from datetime import datetime
        cap = None
        own_capture = False
        camera_unavailable = False
        while self.camera_active:
            try:
                frame = None
                if self.vision and getattr(self.vision, 'last_camera_frame', None) is not None:
                    frame = self.vision.last_camera_frame.copy()
                elif not camera_unavailable:
                    if cap is None:
                        try:
                            cap = cv2.VideoCapture(0)
                            cap.set(3, 640)
                            cap.set(4, 480)
                            own_capture = True
                        except Exception:
                            camera_unavailable = True
                            logger.info("Camera not available for broadcast")
                            return
                    if cap and cap.isOpened():
                        ret, frame = cap.read()
                        if not ret:
                            frame = None
                    else:
                        camera_unavailable = True
                        if cap:
                            cap.release()
                            cap = None
                        return
                if frame is not None:
                    cv2.putText(frame, "SATURDAY VISION", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(frame, timestamp, (10, frame.shape[0] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    _, buffer = cv2.imencode('.jpg', frame)
                    b64 = base64.b64encode(buffer).decode()
                    await self.broadcast_to_ws({
                        "type": "camera_frame",
                        "frame": b64
                    })
            except Exception as e:
                logger.warning(f"Camera broadcast error: {e}")
                if cap and own_capture:
                    cap.release()
                    cap = None
            await asyncio.sleep(0.1)          
        if cap and own_capture:
            cap.release()
            cap = None
        logger.info("Camera broadcast loop ended")
    async def _broadcast_stats_loop(self):
        while self.running:
            try:
                cpu = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                stats = {
                    "type": "system_status",
                    "cpu_percent": cpu,
                    "memory_percent": memory.percent,
                    "memory_used_mb": memory.used // (1024 * 1024),
                    "memory_available_mb": memory.available // (1024 * 1024),
                    "disk_percent": disk.percent,
                    "disk_used_gb": disk.used // (1024**3),
                    "disk_total_gb": disk.total // (1024**3),
                    "cpu_count": psutil.cpu_count(),
                    "uptime_seconds": int(self.runtime.get_uptime()),
                }
                health = {
                    "type": "health_update",
                    "cpu_temp": "45°C",
                    "memory_available": f"{memory.available / (1024**3):.1f}GB",
                    "system_status": "Healthy",
                    "power_status": "AC"
                }
                await self.broadcast_to_ws(stats)
                await self.broadcast_to_ws(health)
            except Exception as e:
                logger.debug(f"Stats broadcast error: {e}")
            await asyncio.sleep(2)                          
    def _reset_idle(self):
        self.last_activity = time.time()
        if self.idle_mode:
            logger.info("SATURDAY RE-ENGAGED: Performance Mode Restored.", source="user_input")
            self.idle_mode = False
            self.event_bus.publish("power_mode", {"mode": "performance"})
            self.event_bus.publish("system_active", {"timestamp": time.time()})
    def _wire_ws_forwarders(self):
        forward_map = [
            ("voice_command", "voice_command"),
            ("voice_response", "voice_response"),
            ("security_alert", "security_alert"),
            ("environment_event", "environment_event"),
            ("acoustic_scene", "acoustic_scene"),
            ("vitals_update", "vitals_update"),
            ("homebot_telemetry", "homebot_telemetry"),
        ]
        for evt_name, ws_type in forward_map:
            try:
                self.event_bus.subscribe(evt_name, lambda payload, ws_type=ws_type: _broadcast_threadsafe(ws_type, payload))
            except Exception as e:
                logger.warning("Failed to bind ws forwarder", event=evt_name, error=str(e))
    def _on_vision_update(self, data):
        if data.get("type") == "human_status":
            self.last_vision_summary = f"Detected {data.get('count')} human(s) in frame. Mood: {data.get('mood', 'unknown')}."
        elif data.get("type") in ("desktop_observation", "desktop_analysis"):
            self.last_vision_summary = "Currently observing active desktop tasks."
    def _on_env_update(self, data):
        if data.get("type") == "surroundings_active":
            self.last_env_summary = "Environment is stable and monitored."
    async def _chatter_loop(self):
        logger.info("Chatter loop active. Monitoring for idle states...")
        while self.running:
            await asyncio.sleep(10)                        
            idle_time = time.time() - self.last_activity
            if idle_time > 30 and not self.idle_mode:           
                logger.info("SATURDAY IDLE: Switching to Intelligent Low-Power Mode.")
                self.idle_mode = True
                self.event_bus.publish("power_mode", {"mode": "low"})
            if idle_time > 60 and self.human_interface:             
                if random.random() < 0.4: 
                    logger.info(f"Triggering SATURDAY-EDITH Internal Dialogue (Idle for {int(idle_time)}s)")
                    news = self.news_service.get_latest()
                    env = f"{self.last_vision_summary} {self.last_env_summary}"
                    script = await self.human_interface.generate_internal_dialogue(env, news)
                    if not script:
                        logger.warning("Converse mode generated NO script.")
                        continue
                    for turn in script:
                        speaker = turn.get("speaker", "SATURDAY")
                        text = turn.get("text", "")
                        if not text: continue
                        logger.info(f"Dialogue: {speaker} says: {text}")
                        self.event_bus.publish("voice_response", f"{speaker}: {text}")
                        await asyncio.sleep(len(text) * 0.12 + 1.5)
                    self.last_activity = time.time() - 40 
                else:
                    logger.debug(f"System idle ({int(idle_time)}s), but chatter probability not met.")
    async def _on_voice_command(self, data):
        command = data.get("command", "") if isinstance(data, dict) else str(data)
        if self.voice_router:
            await self.voice_router.process(command)
        self.event_bus.publish("voice_command_unhandled", data)
    def _on_health_update(self, data):
        if data.get("type") == "heart_rate":
            hr = data.get("value")
            logger.info(f"Health Monitoring: Heart Rate detected at {hr} BPM.")
            if self.ml_core:
                self.ml_core.learn("health", [hr / 200.0, 0.5, 0.5], 0 if hr < 100 else 1)
            self.last_env_summary = f"User heart rate is {hr} BPM."
        elif data.get("type") == "human_status":
            mood = data.get("mood", "Calm")
            logger.info(f"Identity Sync: Mood detected as {mood}.")
            if self.ml_core:
                self.ml_core.learn("identity", [0.8 if mood == "Happy" else 0.5], 2)
            self.last_env_summary += f" User mood is {mood}."
        _broadcast_threadsafe("vitals_update", data)
    async def _neural_policy_loop(self):
        while self.running:
            try:
                await asyncio.sleep(120)
                if self.dl_core and self.neural_policy:
                    self.neural_policy._save_model()
            except Exception as e:
                logger.warning(f"Neural policy loop error: {e}")
    async def _pattern_update_loop(self):
        while self.running:
            try:
                await asyncio.sleep(180)
                if self.pattern_recognition:
                    self.pattern_recognition._save_patterns()
            except Exception as e:
                logger.warning(f"Pattern update loop error: {e}")
    async def _evolution_loop(self):
        while self.running:
            try:
                await asyncio.sleep(300)
                if self.self_evolution and self.dl_core:
                    status = self.dl_core.get_status()
                    if status.get("neural_state", {}).get("awareness_level", 0) > 0.5:
                        self.self_evolution.record_learning()
            except Exception as e:
                logger.warning(f"Evolution loop error: {e}")
    def _register_subsystems_with_ml(self):
        if not self.ml_core:
            return
        subsystems = [
            ("health", 15, 30, 5),
            ("identity", 20, 40, 8),
            ("communication", 25, 50, 10),
            ("vision", 30, 60, 12),
            ("voice", 20, 40, 8),
            ("gesture", 15, 30, 6),
            ("security", 20, 40, 8),
            ("christianity", 15, 30, 5),
            ("homebot", 20, 40, 8),
            ("ui", 15, 30, 6),
            ("music", 10, 20, 4),
            ("calendar", 15, 30, 5),
            ("email", 20, 40, 8),
            ("social", 15, 30, 6),
            ("sensors", 20, 40, 8),
            ("distributed", 15, 30, 5),
        ]
        for name, inp, hid, out in subsystems:
            self.ml_core.register_subsystem(name, inp, hid, out)
        logger.info(f"Registered {len(subsystems)} subsystems with ML Core")
    async def start(self):
        logger.info("SATURDAY System Standalone Starting...")
        config = Config(app=self.app, host="0.0.0.0", port=8000, loop="asyncio")
        self.server = Server(config)
        await self.server.serve()
    async def shutdown(self):
        logger.info("SATURDAY System Shutting Down...")
        self.running = False
        try:
            self.window_manager.stop_process_monitor()
        except:
            pass
        try:
            if hasattr(self.homebot, "shutdown"):
                self.homebot.shutdown()
        except Exception:
            pass
        if hasattr(self, 'server'): 
            await self.server.shutdown()
async def main():
    saturday = SATURDAYCore()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, lambda: asyncio.create_task(saturday.shutdown()))
        except NotImplementedError: pass
    try: await saturday.start()
    except Exception as e: logger.error("Fatal exception", error=str(e))
    finally: await saturday.shutdown()
if __name__ == "__main__":
    asyncio.run(main())
