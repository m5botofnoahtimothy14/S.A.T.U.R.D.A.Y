# core/main.py
import asyncio
import signal
import sys
import os
import structlog
import json
import base64
import psutil
import random
import time
import logging
from threading import Thread
from fastapi import FastAPI, Request, WebSocket, APIRouter, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from uvicorn import Config, Server
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import auth as fb_auth

# Path setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.event_bus import EventBus
from core.runtime import RuntimeStats
from core.config import ConfigManager
from core.state import SystemState
from core.rbac import RBAC
from health.monitor import HealthMonitor
from governance.policy import PolicyEngine
from identity.manager import IdentityManager
from identity.face_id import FaceID
from identity.voice_id import VoiceID
from ui.bridge import WebUI
from ui.voice_interface import VoiceInterface
from core.human_interface import HumanInterface
from core.cloud_bridge import CloudBridge
from ai_modules.llm_engine import LLMEngine
from communication.speech import SpeechManager
from communication.call_agent import CallAgent
from communication.livekit_webhooks import register_livekit_webhooks
from embodied.vision import VisionModule
from christianity_core.spirituality import ChristianityCore
from core.homebot_integration import HomeBotIntegration
from hybrid.main import HybridManager
from hybrid.edith.main import EDITH
from core.sound_monitor import SoundMonitor
from core.alert_manager import AlertManager
from core.brain import LinkedBrain
from core.greeting import GreetingManager
from core.spatial_audio import SpatialAudioEngine
from core.task_manager import TaskManager
from core.window_manager import WindowManager
from core.self_heal import SelfHealManager
from core.self_healing import SelfHealing
from core.admin_mood import AdminMood
from core.self_rewrite import SelfRewriteAdvisor

from core.voice_dl import AEGISVoiceDL

from deep_learning.core import DeepLearningCore
from deep_learning.policy import NeuralPolicyEngine
from deep_learning.adaptive import AdaptiveLearningEngine
from deep_learning.patterns import PatternRecognition
from deep_learning.evolution import SelfEvolution
from ml_integration.core import MLIntegrationCore
from ml_integration.predictor import PredictiveEngine
from ml_integration.nlp import NLPEngine
from conversational_dl.engine import ConversationalDLEngine

from services.web_search import WebSearchService
from services.music_manager import MusicManager
from services.weather_service import WeatherService
from core.learning_manager import LearningManager
from core.usb_watchdog import USBWatchdog
from core.remote_desktop import RemoteDesktopManager
from ai_modules.security_assistant import SecurityAssistant
from core.engagement import EngagementManager
from core.system_tray import SystemTray

from services.news_service import NewsService
from communication.screen_navigator import ScreenNavigator
from communication.social_agent import SocialAgent
from communication.voice_command_router import VoiceCommandRouter
from communication.whatsapp_navigator import WhatsAppNavigator
from communication.insta_navigator import InstaNavigator
from distributed import InterDeviceSync, DeviceRegistry, RemoteControl, SessionMirror
from core.secure_gateway_mount import try_mount_secure_gateway

# Face database storage
FACE_DB_FILE = "data/faces.json"
DIRECTORY_FILE = "data/directory.json"
VOICE_PROFILES_FILE = "data/voice_profiles.json"

os.makedirs("data", exist_ok=True)

# Module-level FastAPI app for uvicorn
app = None

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

# Logging - Setup centralized logging
from core.logging_config import setup_aegis_logging, AEGISLogger, get_log_file_path
setup_aegis_logging()

# Configure structlog to use the main aegis.log
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)

# Create a logging handler that writes to both main and subsystem logs
class SubsystemFileHandler(logging.Handler):
    def __init__(self, subsystem=None):
        super().__init__()
        self.subsystem = subsystem
        
    def emit(self, record):
        try:
            msg = self.format(record)
            # Write to main log
            with open(f"{LOG_DIR}/aegis.log", "a") as f:
                f.write(msg + "\n")
            # Write to subsystem log if applicable
            if self.subsystem:
                sub_path = get_log_file_path(self.subsystem)
                with open(sub_path, "a") as f:
                    f.write(msg + "\n")
        except Exception:
            self.handleError(record)

# Configure root logger
root_logger = logging.getLogger("AEGIS")
root_logger.setLevel(logging.DEBUG)
root_logger.propagate = False

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
has_main_file_handler = any(
    isinstance(h, logging.FileHandler) and os.path.basename(getattr(h, "baseFilename", "")) == "aegis.log"
    for h in root_logger.handlers
)
if not has_main_file_handler and not any(isinstance(h, SubsystemFileHandler) for h in root_logger.handlers):
    handler = SubsystemFileHandler()
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

# Also add console handler
if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root_logger.handlers):
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root_logger.addHandler(console)

# Keep structlog for event bus JSON logging
if not getattr(structlog, "_aegis_configured", False):
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"), 
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.WriteLoggerFactory(file=open(f"{LOG_DIR}/aegis.log", "a")),
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
    )
    structlog._aegis_configured = True
logger = structlog.get_logger("AEGIS.Core")

# Create FastAPI app at module level for uvicorn
app = FastAPI(title="AEGIS AI OS")
templates = Jinja2Templates(directory="ui/templates")
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
    return os.getenv("AEGIS_DISABLE_AUTH", "false").strip().lower() in {"1", "true", "yes", "on"}

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
    if _aegis_core is None:
        raise HTTPException(status_code=503, detail="AEGIS core is not initialized")
    return _aegis_core

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
        if _aegis_core and getattr(_aegis_core, "loop", None):
            asyncio.run_coroutine_threadsafe(_broadcast(event_type, data), _aegis_core.loop)
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
async def wake_aegis():
    core = _require_core()
    try:
        core.event_bus.publish("voice_command", "aegis")
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
    path = os.path.join("logs", "aegis.log")
    if not os.path.exists(path):
        return {"lines": []}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()[-limit:]
    return {"lines": [l.rstrip('\n') for l in lines]}


@router.get("/voice/logs", dependencies=[Depends(verify_firebase_token)])
async def voice_logs(limit: int = 50):
    path = os.path.join("logs", "aegis.log")
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
            # Keep the connection open; we don't require inbound messages
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        connected_websockets.discard(websocket)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API router
app.include_router(router)

# Optional secure gateway mount (Firebase/JWT/LangGraph/ROS2 control plane)
_secure_gateway_mount_status = try_mount_secure_gateway(app, logger)

# Global AEGISCore instance
_aegis_core = None

@app.on_event("startup")
async def startup_event():
    global _aegis_core
    if _aegis_core is None:
        _aegis_core = AEGISCore()

@app.on_event("shutdown")
async def shutdown_event():
    global _aegis_core
    if _aegis_core:
        _aegis_core.running = False
        try:
            await _aegis_core.shutdown()
        except Exception as e:
            logger.warning(f"Startup/shutdown lifecycle cleanup failed: {e}")

class AEGISCore:
    def __init__(self):
        load_dotenv()
        
        # Use module-level app
        self.app = app
        self.templates = templates
        self.websockets = []
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = None
        
        self.event_bus = EventBus()
        self.runtime = RuntimeStats()
        self.config_manager = ConfigManager()
        self.strict_prod = os.getenv("AEGIS_STRICT_PROD", "false").strip().lower() in {
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

        # System states
        self.security_enabled = True
        self.vision_enabled = True
        self.voice_enabled = True
        self.faceid_enabled = True
        self.camera_active = False
        self._camera_task = None
        
        # Inactivity & Intelligence
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
        self.event_bus.subscribe("vitals_update", self._on_health_update)
        self._wire_ws_forwarders()
        
        # Screen & Social Agents
        self.screen = ScreenNavigator(self.event_bus)
        self.social_agent = None # Initialized after HumanInterface
        
        # Dependency Injection / Module Instantiation - all wrapped in try/except
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
            self.sound_monitor = SoundMonitor(self.event_bus)
        except Exception as e:
            logger.warning(f"SoundMonitor init failed: {e}")
            self.sound_monitor = None
        
        try:
            self.spirituality = ChristianityCore(self.event_bus)
        except Exception as e:
            logger.warning(f"ChristianityCore init failed: {e}")
            self.spirituality = None
        
        try:
            self.homebot = HomeBotIntegration(self.event_bus)
        except Exception as e:
            logger.warning(f"HomeBotIntegration init failed: {e}")
            self.homebot = None
        
        try:
            self.ui = WebUI(self.event_bus)
        except Exception as e:
            logger.warning(f"WebUI init failed: {e}")
            self.ui = None
        
        try:
            self.voice = VoiceInterface(self.event_bus)
        except Exception as e:
            logger.warning(f"VoiceInterface init failed: {e}")
            self.voice = None
        
        # Linked Intelligence
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
        
        # Advanced OS Subsystems
        try:
            self.spatial_audio = SpatialAudioEngine(self.event_bus)
        except Exception as e:
            logger.warning(f"SpatialAudioEngine init failed: {e}")
            self.spatial_audio = None
        
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
        
        # Optional modules
        try:
            self.learning = LearningManager(self.event_bus, self.ai, self.task_manager)
        except Exception as e:
            logger.warning(f"LearningManager init failed: {e}")
            self.learning = None
        
        # Deep Learning Core - Neural Network AI Engine
        try:
            self.dl_core = DeepLearningCore(self.event_bus)
            logger.info("Deep Learning Core initialized - AEGIS is now a DL-powered AI")
        except Exception as e:
            logger.warning(f"DeepLearningCore init failed: {e}")
            self.dl_core = None
        
        # Neural Policy Engine - DL-enhanced governance
        try:
            self.neural_policy = NeuralPolicyEngine(self.event_bus, self.dl_core)
        except Exception as e:
            logger.warning(f"NeuralPolicyEngine init failed: {e}")
            self.neural_policy = None
        
        # Adaptive Learning Engine - Continuous learning
        try:
            self.adaptive_learning = AdaptiveLearningEngine(self.event_bus, self.dl_core)
        except Exception as e:
            logger.warning(f"AdaptiveLearningEngine init failed: {e}")
            self.adaptive_learning = None
        
        # Pattern Recognition - User behavior neural network
        try:
            self.pattern_recognition = PatternRecognition(self.event_bus, self.dl_core)
        except Exception as e:
            logger.warning(f"PatternRecognition init failed: {e}")
            self.pattern_recognition = None
        
        # Self Evolution - Self-improvement framework
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
        
        # ML Integration Core - Unified ML/DL for ALL subsystems
        try:
            self.ml_core = MLIntegrationCore(self.event_bus)
            logger.info("ML Integration Core initialized - All subsystems now use ML/DL")
        except Exception as e:
            logger.warning(f"MLIntegrationCore init failed: {e}")
            self.ml_core = None
        
        # NLP Engine - Deep Learning for voice understanding
        try:
            self.nlp_engine = NLPEngine(self.event_bus)
            logger.info("NLP Engine initialized - Voice commands now use DL NLP")
        except Exception as e:
            logger.warning(f"NLPEngine init failed: {e}")
            self.nlp_engine = None
        
        # Predictive Engine - ML predictions for all systems
        try:
            self.predictor = PredictiveEngine(self.event_bus)
        except Exception as e:
            logger.warning(f"PredictiveEngine init failed: {e}")
            self.predictor = None
        
        # Conversational DL Engine - True Conversational AI
        try:
            self.conversation = ConversationalDLEngine(self.event_bus, self)
            logger.info("Conversational DL Engine initialized - AEGIS is now truly conversational!")
        except Exception as e:
            logger.warning(f"ConversationalDLEngine init failed: {e}")
            self.conversation = None
        
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
            self.alerts = AlertManager(self.event_bus)
        except Exception as e:
            logger.warning(f"AlertManager init failed: {e}")
            self.alerts = None
        
        try:
            self.hybrid = HybridManager(self.event_bus, self.ai)
        except Exception as e:
            logger.warning(f"HybridManager init failed: {e}")
            self.hybrid = None
        
        # Distributed Mesh Components
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
        
        # Phase D: LiveKit Streaming Hooks
        self.livekit = None
        if self.config_manager.get("ai.use_livekit", False):
            try:
                from communication.livekit_bridge import LiveKitBridge
                self.livekit = LiveKitBridge(self.event_bus)
                asyncio.create_task(self.livekit.start())
                logger.info("LiveKit bridge enabled and starting.")
            except Exception as e:
                logger.warning(f"LiveKit bridge failed to initialize: {e}")
                self.livekit = None
        
        # Phase E: ROS2 Bridge
        self.ros2 = None
        if self.config_manager.get("ai.use_ros2", False):
            try:
                from integration.ros2_bridge import ROS2Bridge
                self.ros2 = ROS2Bridge(self.event_bus)
                asyncio.create_task(self.ros2.start())
                logger.info("ROS2 bridge enabled and starting.")
            except Exception as e:
                logger.warning(f"ROS2 bridge failed to initialize: {e}")
                self.ros2 = None
        
        # Phase F: Sync Node
        self.sync_node = None
        if self.config_manager.get("ai.use_sync", False):
            try:
                from integration.sync_node import StateSyncNode
                self.sync_node = StateSyncNode(self.event_bus, self.runtime)
                asyncio.create_task(self.sync_node.start())
                logger.info("Sync Node enabled and starting.")
            except Exception as e:
                logger.warning(f"Sync Node failed to initialize: {e}")
                self.sync_node = None
        
        # Human Interface
        try:
            from core.human_interface import HumanInterface
            self.human_interface = HumanInterface(self.event_bus, self.ai, self.speech, self.task_manager, self.learning)
        except Exception as e:
            logger.warning(f"HumanInterface init failed: {e}")
            self.human_interface = None
        
        # AEGIS Voice DL - Full System Control Voice Interface
        try:
            from core.voice_dl import AEGISVoiceDL
            self.voice_dl = AEGISVoiceDL(self.event_bus, self.ai, self.speech)
            logger.info("AEGIS Voice DL initialized - Full system control ready")
        except Exception as e:
            logger.warning(f"AEGISVoiceDL init failed: {e}")
            self.voice_dl = None

        # Capture language hints from ASR
        try:
            def handle_speech_lang(payload):
                if payload and self.human_interface:
                    lang = payload.get("lang")
                    if lang:
                        self.human_interface.set_language_hint(lang)
            self.event_bus.subscribe("speech_lang", handle_speech_lang)
        except Exception as e:
            logger.warning("Failed to bind speech_lang handler", error=str(e))

        # Speak out any voice_response events to keep AEGIS lively
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

        # Web search + mood music services
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
        
        # System Tray
        self.system_tray = None
        try:
            self.system_tray = SystemTray(self)
            logger.info("System tray initialized")
        except Exception as e:
            logger.warning(f"System tray init failed: {e}")
        
        self.setup_routes()
        self.running = True
        
        # Module-level self-healing (crashed process recovery) - Init late to capture all objects
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

        # Specialized Voice Routing
        try:
            self.whatsapp_nav = WhatsAppNavigator()
            self.insta_nav = InstaNavigator()
            self.voice_router = VoiceCommandRouter(self.event_bus, self.speech, self.whatsapp_nav, self.insta_nav)
            self.event_bus.subscribe("voice_command", lambda d: asyncio.create_task(self.voice_router.process(d.get("command", "") if isinstance(d, dict) else str(d))))
        except Exception as e:
            logger.warning(f"Voice Router initialization failed: {e}")

        # Start all background autonomous loops
        # Expose AEGISCore on the FastAPI app for routers needing context
        self.app.aegis = self

        # Cloud Bridge for Remote Control
        self.cloud_bridge = None
        firebase_project_id = self._firebase_project_id()
        if firebase_project_id:
            self.cloud_bridge = CloudBridge(self.event_bus, firebase_project_id)

        try:
             self.social_agent = SocialAgent(self.event_bus, self.human_interface)
             logger.info("Social Agent registered with HumanInterface.")
        except Exception as e:
             logger.warning(f"Social Agent init failed: {e}")

        logger.info("Validating production state", strict_prod=self.strict_prod)
        self._validate_production_state()

        # Start all background autonomous loops only after strict validation passes.
        self.start_background_loops()

        # Forward key events to WebSocket clients
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
        
        logger.info("AEGIS Core initialized successfully")

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

        if os.getenv("AEGIS_ENABLE_SECURE_GATEWAY_MOUNT", "false").strip().lower() in {"1", "true", "yes", "on"}:
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
        """Always greet on startup using configured user mode (Sir/Noah)."""
        title = self._preferred_user_title()
        self.event_bus.publish("voice_response", f"AEGIS OS online. Welcome back, {title}.")

    def start_background_loops(self):
        """Starts ALL autonomous background cycles in AEGIS."""
        logger.info("Starting background autonomous loops...")
        
        # Core health & self-heal
        if self.health:
            asyncio.create_task(self.health.start())
            logger.info("Health monitoring loop started.")
            
        if self.self_heal:
            asyncio.create_task(self.self_heal.start())
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

        # Core Vision - Camera & Screen
        if self.vision:
            try:
                asyncio.create_task(self.vision.start())
                logger.info("Vision System loops started.")
            except Exception as e:
                logger.warning(f"Vision System failed to start: {e}")

        # Real-time stats broadcast to WebSocket clients
        asyncio.create_task(self._broadcast_stats_loop())
        logger.info("Stats broadcast loop started.")

        # Sound monitor (microphone)
        if self.sound_monitor:
            try:
                self.sound_monitor.start()
                logger.info("Sound monitor started.")
            except Exception as e:
                logger.warning(f"Sound monitor could not start: {e}")

        # Hybrid services (wake word, etc.)
        if self.hybrid:
            try:
                asyncio.create_task(self.hybrid.start())
                logger.info("Hybrid services started.")
            except Exception as e:
                logger.warning(f"Hybrid start failed: {e}")

        # Engagement manager
        if self.engagement:
            try:
                self.engagement.start()
                logger.info("Engagement manager started.")
            except Exception as e:
                logger.warning(f"Engagement start failed: {e}")

        # USB watchdog
        if self.usb_watchdog:
            try:
                self.usb_watchdog.start()
                logger.info("USB watchdog started.")
            except Exception as e:
                logger.warning(f"USB watchdog start failed: {e}")

        # System tray
        if self.system_tray:
            try:
                self.system_tray.start()
                logger.info("System tray started.")
            except Exception as e:
                logger.warning(f"System tray start failed: {e}")

        # Deep Learning autonomous learning loops
        if self.dl_core:
            asyncio.create_task(self.dl_core.start_autonomous_learning())
            asyncio.create_task(self.dl_core.start_periodic_save())
            logger.info("Deep Learning Core autonomous loops started.")
        
        # Neural policy background learning
        if self.neural_policy and self.dl_core:
            asyncio.create_task(self._neural_policy_loop())
            logger.info("Neural Policy learning loop started.")
        
        # Pattern recognition autonomous updates
        if self.pattern_recognition:
            asyncio.create_task(self._pattern_update_loop())
            logger.info("Pattern Recognition loop started.")
        
        # Self evolution monitoring
        if self.self_evolution:
            asyncio.create_task(self._evolution_loop())
            logger.info("Self Evolution loop started.")
        
        # ML Integration Core - All subsystems learning
        if self.ml_core:
            asyncio.create_task(self.ml_core.start_autonomous_learning())
            asyncio.create_task(self.ml_core.start_periodic_save())
            self._register_subsystems_with_ml()
            logger.info("ML Integration Core learning loops started.")
        
        # NLP Engine
        if self.nlp_engine:
            logger.info("NLP Engine active for voice understanding.")
        
        # Predictive Engine
        if self.predictor:
            logger.info("Predictive Engine active.")

        # Conversational chatter loop
        asyncio.create_task(self._chatter_loop())

        # Vision event handler
        self.event_bus.subscribe("vision_event", lambda data: asyncio.create_task(self._on_vision_event(data)) if isinstance(data, dict) else None)
        self.event_bus.subscribe("camera_start", lambda _: asyncio.create_task(self.vision.start_stream()) if self.vision else None)
        self.event_bus.subscribe("camera_stop", lambda _: asyncio.create_task(self.vision.stop_stream()) if self.vision else None)

        if self.social_agent:
            asyncio.create_task(self.social_agent.start_monitoring())
            logger.info("Social/Gmail monitor started.")

        cloud_bridge = getattr(self, "cloud_bridge", None)
        if cloud_bridge:
            asyncio.create_task(cloud_bridge.start())
            logger.info("Cloud Bridge remote listener started.")

        logger.info("All background loops initiated.")

    def _on_sound_update(self, data):
        level = data.get("level_db", 0)
        if level > 60:
            self.last_env_summary = f"Detected noise level of {level}dB in the workspace."

    async def _wake_target(self, target: str, source: str = "local", requested_by: str | None = None):
        normalized = str(target).strip().lower()
        if normalized not in {"aegis", "edith"}:
            return {
                "success": False,
                "target": normalized,
                "source": source,
                "requested_by": requested_by,
                "message": "Invalid wake target. Use 'aegis' or 'edith'.",
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
            self.event_bus.publish("voice_command", "edith")
            self.event_bus.publish(
                "edith_wake_command",
                {"source": source, "requested_by": requested_by, "target": "edith"},
            )
            message = "EDITH wake signal sent."
        else:
            self.event_bus.publish(
                "wake_command",
                {"source": source, "requested_by": requested_by, "target": "aegis"},
            )
            # This also deactivates EDITH mode when active.
            self.event_bus.publish("voice_command", "aegis")
            self.event_bus.publish("voice_response", "AEGIS wake signal received.")
            message = "AEGIS wake signal sent."

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
            return self.templates.TemplateResponse("index.html", {"request": request})

        @self.app.get("/api/debug")
        async def api_debug():
            return {
                "status": "ok",
                "runtime": self.runtime is not None,
                "event_bus": self.event_bus is not None,
                "initialized": True
            }

        @self.app.get("/api/secure/mount-status")
        async def api_secure_mount_status():
            return _secure_gateway_mount_status

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.websockets.append(websocket)
            # Send initial status including EDITH readiness
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
                    "disk_percent": psutil.disk_usage(os.getenv('SystemDrive', 'C:\\')).percent
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
        @self.app.get("/api/vitals")
        async def api_vitals():
            # Parse the last_env_summary for HR and Mood from DL engines
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
            faces = load_json_db(FACE_DB_FILE)
            return faces

        @self.app.post("/api/face/train")
        async def api_face_train(data: dict):
            faces = load_json_db(FACE_DB_FILE)
            if len(faces) >= 10:
                return {"success": False, "error": "Maximum 10 faces allowed"}
            
            new_face = {
                "id": len(faces) + 1,
                "name": data.get("name"),
                "relation": data.get("relation"),
                "photos": data.get("photos", []),
                "photo": data.get("photos", [None])[0] if data.get("photos") else None,
                "trained": True
            }
            faces.append(new_face)
            save_json_db(FACE_DB_FILE, faces)
            self.event_bus.publish("face_trained", new_face)
            return {"success": True, "face": new_face}

        @self.app.delete("/api/face/{face_id}")
        async def api_face_delete(face_id: int):
            faces = load_json_db(FACE_DB_FILE)
            faces = [f for f in faces if f.get("id") != face_id]
            save_json_db(FACE_DB_FILE, faces)
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

        @self.app.get("/api/voice/list")
        async def api_voice_list():
            profiles = load_json_db(VOICE_PROFILES_FILE)
            return profiles

        @self.app.post("/api/voice/train")
        async def api_voice_train(data: dict):
            profiles = load_json_db(VOICE_PROFILES_FILE)
            new_profile = {
                "id": len(profiles) + 1,
                "name": data.get("name"),
                "samples": data.get("samples", 0),
                "trained": True
            }
            profiles.append(new_profile)
            save_json_db(VOICE_PROFILES_FILE, profiles)
            return {"success": True, "profile": new_profile}

        @self.app.post("/api/control/wake")
        async def api_wake(data: dict | None = None):
            payload = data or {}
            target = payload.get("target", "aegis")
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
            # Start broadcasting camera frames
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
            async for chunk in self.ai.chat_stream(prompt): response += chunk
            return {"response": response}

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

        # Deep Learning System API Routes
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

        # ML Integration API Routes
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

        # NLP Engine API Routes
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

        # Predictive Engine API Routes
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

        # Conversational DL Engine API Routes
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

        # Telephony / call automation routes
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
        
        elif msg_type in ("wake_aegis", "wake_edith"):
            target = "edith" if msg_type == "wake_edith" else "aegis"
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
        
        elif msg_type == "restart_aegis":
            self.event_bus.publish("restart_command", {})
            await self.broadcast_to_ws({"type": "voice_msg", "text": "Restarting AEGIS systems"})
        
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
  wake              - Wake AEGIS
  wake edith        - Wake EDITH interface
  scan              - Run security scan
  secure status     - Secure gateway mount status
  clear             - Clear screen"""
        
        elif cmd == "status":
            stats = self.runtime.get_resource_usage()
            return f"""AEGIS System Status
Version: 2.0.0
CPU: {psutil.cpu_percent()}%
Memory: {psutil.virtual_memory().percent}%
Disk: {psutil.disk_usage(os.getenv('SystemDrive', 'C:\\')).percent}%
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
            du = psutil.disk_usage(os.getenv('SystemDrive', 'C:\\'))
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
        
        elif cmd in ("wake", "wake aegis"):
            result = await self._wake_target(target="aegis", source="terminal")
            return result.get("message", "AEGIS wake command dispatched")

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
        cap.set(3, 640)  # Width
        cap.set(4, 480)  # Height
        
        try:
            while self.camera_active:
                ret, frame = cap.read()
                if ret:
                    # Add AEGIS overlay
                    cv2.putText(frame, "AEGIS VISION", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    
                    _, buffer = cv2.imencode('.jpg', frame)
                    b64 = base64.b64encode(buffer).decode()
                    
                    await websocket.send_json({
                        "type": "camera_frame",
                        "frame": b64
                    })
                await asyncio.sleep(0.05)  # ~20fps
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
        """Broadcast camera frames to all connected websockets.
        
        Uses VisionModule's existing frame buffer when available to avoid
        opening a duplicate camera capture that conflicts on Windows.
        """
        import cv2
        from datetime import datetime
        cap = None
        own_capture = False
        
        while self.camera_active:
            try:
                frame = None
                # Prefer VisionModule's already-captured frame
                if self.vision and getattr(self.vision, 'last_camera_frame', None) is not None:
                    frame = self.vision.last_camera_frame.copy()
                else:
                    # Fallback: open our own capture only if vision isn't running
                    if cap is None:
                        cap = cv2.VideoCapture(0)
                        cap.set(3, 640)
                        cap.set(4, 480)
                        own_capture = True
                    ret, frame = cap.read()
                    if not ret:
                        frame = None
                
                if frame is not None:
                    # Add AEGIS overlay
                    cv2.putText(frame, "AEGIS VISION", (10, 30), 
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
            
            await asyncio.sleep(0.1)  # ~10fps
        
        if cap and own_capture:
            cap.release()
            cap = None
        logger.info("Camera broadcast loop ended")

    async def _broadcast_stats_loop(self):
        """Broadcast real-time system stats to all connected clients"""
        while self.running:
            try:
                # Get current system stats
                cpu = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage(os.getenv('SystemDrive', 'C:\\'))
                
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
                
                # Also get health data
                health = {
                    "type": "health_update",
                    "cpu_temp": "45°C",
                    "memory_available": f"{memory.available / (1024**3):.1f}GB",
                    "system_status": "Healthy",
                    "power_status": "AC"
                }
                
                # Broadcast both
                await self.broadcast_to_ws(stats)
                await self.broadcast_to_ws(health)
                
            except Exception as e:
                logger.debug(f"Stats broadcast error: {e}")
            
            await asyncio.sleep(2)  # Update every 2 seconds

    def _reset_idle(self):
        self.last_activity = time.time()
        if self.idle_mode:
            logger.info("AEGIS RE-ENGAGED: Performance Mode Restored.", source="user_input")
            self.idle_mode = False
            # Signal modules to wake up
            self.event_bus.publish("power_mode", {"mode": "performance"})
            self.event_bus.publish("system_active", {"timestamp": time.time()})

    def _wire_ws_forwarders(self):
        """Forward key events to any connected WebSocket clients for the dashboard."""
        forward_map = [
            ("voice_command", "voice_command"),
            ("voice_response", "voice_response"),
            ("security_alert", "security_alert"),
            ("environment_event", "environment_event"),
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
        """Autonomous Dialogue Engine: AEGIS & EDITH"""
        logger.info("Chatter loop active. Monitoring for idle states...")
        while self.running:
            await asyncio.sleep(10) # Check more frequently
            
            idle_time = time.time() - self.last_activity
            
            # 1. Power Management (Intelligent Mode)
            if idle_time > 30 and not self.idle_mode: # 30s idle
                logger.info("AEGIS IDLE: Switching to Intelligent Low-Power Mode.")
                self.idle_mode = True
                self.event_bus.publish("power_mode", {"mode": "low"})

            # 2. Converse Mode (Internal Dialogue)
            if idle_time > 60 and self.human_interface: # 1 min idle
                # Increased probability for first turn, then jitter handles it
                if random.random() < 0.4: 
                    logger.info(f"Triggering AEGIS-EDITH Internal Dialogue (Idle for {int(idle_time)}s)")
                    news = self.news_service.get_latest()
                    env = f"{self.last_vision_summary} {self.last_env_summary}"
                    
                    script = await self.human_interface.generate_internal_dialogue(env, news)
                    
                    if not script:
                        logger.warning("Converse mode generated NO script.")
                        continue

                    for turn in script:
                        speaker = turn.get("speaker", "AEGIS")
                        text = turn.get("text", "")
                        if not text: continue
                        
                        logger.info(f"Dialogue: {speaker} says: {text}")
                        self.event_bus.publish("voice_response", f"{speaker}: {text}")
                        # Wait for them to "speak"
                        await asyncio.sleep(len(text) * 0.12 + 1.5)
                    
                    # Reset jitter to prevent constant chatter
                    self.last_activity = time.time() - 40 
                else:
                    logger.debug(f"System idle ({int(idle_time)}s), but chatter probability not met.")

    async def _on_voice_command(self, data):
        """Routes voice commands to the router and AI engine."""
        command = data.get("command", "") if isinstance(data, dict) else str(data)
        
        # Route through specialty router first (WhatsApp, Screen, etc.)
        if self.voice_router:
            await self.voice_router.process(command)
        
        # Also let HumanInterface process for conversation
        self.event_bus.publish("voice_command_unhandled", data)

    def _on_health_update(self, data):
        """Unified health update handler - processes heart rate, mood, and ML learning."""
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
        """Neural policy learning loop"""
        while self.running:
            try:
                await asyncio.sleep(120)
                if self.dl_core and self.neural_policy:
                    self.neural_policy._save_model()
            except Exception as e:
                logger.warning(f"Neural policy loop error: {e}")
                
    async def _pattern_update_loop(self):
        """Pattern recognition update loop"""
        while self.running:
            try:
                await asyncio.sleep(180)
                if self.pattern_recognition:
                    self.pattern_recognition._save_patterns()
            except Exception as e:
                logger.warning(f"Pattern update loop error: {e}")
                
    async def _evolution_loop(self):
        """Self evolution monitoring loop"""
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
        """Register all AEGIS subsystems with ML Core"""
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
        """Standalone entry point - starts background loops and then the web server."""
        logger.info("AEGIS System Standalone Starting...")
        
        # Background loops are already started in __init__
        
        config = Config(app=self.app, host="0.0.0.0", port=8000, loop="asyncio")
        self.server = Server(config)
        await self.server.serve()

    async def shutdown(self):
        logger.info("AEGIS System Shutting Down...")
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
    aegis = AEGISCore()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, lambda: asyncio.create_task(aegis.shutdown()))
        except NotImplementedError: pass

    try: await aegis.start()
    except Exception as e: logger.error("Fatal exception", error=str(e))
    finally: await aegis.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
