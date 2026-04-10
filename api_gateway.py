from __future__ import annotations
import asyncio
import json
import logging
import os
import ssl
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypedDict
from urllib import error as urllib_error
from urllib import request as urllib_request
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field
from auth_validator import AuthenticatedUser, FirebaseAuthValidator
from command_policy import CommandPolicy, PolicyViolation, SafetyLimits
from ros_safety_bridge import BridgeLimits, ROSSafetyBridge
from telemetry_sync import TelemetrySync
from core.event_bus import EventBus
from core.system_monitor import SystemMonitor
from core.ai_agent import get_ai_agent, AIAgent
load_dotenv()
logger = logging.getLogger("aegis.api_gateway")
if not logger.handlers:
    log_level = os.getenv("AEGIS_GATEWAY_LOG_LEVEL", "INFO").upper()
    logger.setLevel(log_level)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    os.makedirs("logs", exist_ok=True)
    file_handler = logging.FileHandler(os.getenv("AEGIS_GATEWAY_LOG_FILE", "logs/api_gateway.log"))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: str = Field(..., description="High-level command intent")
    parameters: dict[str, Any] = Field(default_factory=dict)
class CommandResponse(BaseModel):
    accepted: bool
    trace: list[str]
    result: dict[str, Any]
    executed_at: str
class WakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str = Field(..., description="Wake target: aegis or edith")
    source: str = Field(default="remote_control_panel", min_length=1, max_length=64)
class CommandGraphState(TypedDict, total=False):
    command: dict[str, Any]
    user_uid: str
    user_roles: tuple[str, ...]
    validated_command: dict[str, Any]
    action_plan: list[dict[str, Any]]
    execution_result: dict[str, Any]
    trace: list[str]
@dataclass
class RuntimeState:
    node_id: str
    mode: str = "IDLE"
    status: str = "BOOTING"
    command_count: int = 0
    failed_command_count: int = 0
    last_command_intent: str | None = None
    last_error: str | None = None
    last_operator_uid: str | None = None
    last_heartbeat: str | None = None
    active_tasks: list[dict[str, Any]] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    async def mark_online(self) -> None:
        async with self._lock:
            self.status = "ONLINE"
            self.last_heartbeat = datetime.now(timezone.utc).isoformat()
    async def mark_command_started(self, *, intent: str, operator_uid: str) -> None:
        async with self._lock:
            self.status = "BUSY"
            self.last_command_intent = intent
            self.last_operator_uid = operator_uid
            self.last_error = None
            self.active_tasks = [
                {
                    "id": f"cmd-{self.command_count + self.failed_command_count + 1}",
                    "name": f"Execute {intent}",
                    "state": "RUNNING",
                    "progress": 25,
                }
            ]
            self.last_heartbeat = datetime.now(timezone.utc).isoformat()
    async def mark_command_done(self, *, success: bool, error: str | None = None, mode: str | None = None) -> None:
        async with self._lock:
            if success:
                self.command_count += 1
                self.status = "ONLINE"
                self.active_tasks = []
                if mode:
                    self.mode = mode
            else:
                self.failed_command_count += 1
                self.status = "DEGRADED"
                self.last_error = error
                self.active_tasks = [
                    {
                        "id": f"failed-{self.command_count + self.failed_command_count}",
                        "name": "Safety intervention",
                        "state": "FAILED",
                        "progress": 100,
                    }
                ]
            self.last_heartbeat = datetime.now(timezone.utc).isoformat()
    async def snapshot(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        async with self._lock:
            agent_state = {
                "node_id": self.node_id,
                "status": self.status,
                "mode": self.mode,
                "command_count": self.command_count,
                "failed_command_count": self.failed_command_count,
                "last_command_intent": self.last_command_intent,
                "last_operator_uid": self.last_operator_uid,
                "last_error": self.last_error,
                "last_heartbeat": self.last_heartbeat,
                "active_pipeline": "LangGraph-Core",
            }
            return agent_state, list(self.active_tasks)
class CommandExecutionEngine:
    def __init__(self, *, policy: CommandPolicy, ros_bridge: ROSSafetyBridge, telemetry: TelemetrySync) -> None:
        self.policy = policy
        self.ros_bridge = ros_bridge
        self.telemetry = telemetry
        self.graph = self._compile_graph()
    def _compile_graph(self):
        graph = StateGraph(CommandGraphState)
        graph.add_node("policy_gate", self._policy_gate_node)
        graph.add_node("reasoning", self._reasoning_node)
        graph.add_node("execute", self._execute_node)
        graph.add_node("audit", self._audit_node)
        graph.set_entry_point("policy_gate")
        graph.add_edge("policy_gate", "reasoning")
        graph.add_edge("reasoning", "execute")
        graph.add_edge("execute", "audit")
        graph.add_edge("audit", END)
        return graph.compile()
    def _policy_gate_node(self, state: CommandGraphState) -> dict[str, Any]:
        runtime_context = self.ros_bridge.get_runtime_context()
        validated = self.policy.validate_and_enforce(
            command=state["command"],
            roles=state["user_roles"],
            runtime_context=runtime_context,
        )
        trace = list(state.get("trace", []))
        trace.append("policy_gate:passed")
        return {"validated_command": validated, "trace": trace}
    def _reasoning_node(self, state: CommandGraphState) -> dict[str, Any]:
        command = state["validated_command"]
        intent = command["intent"]
        params = command["parameters"]
        if intent == "MOVE":
            actions = [
                {"step": "safety_precheck", "direction": params["direction"]},
                {
                    "step": "motion_execute",
                    "direction": params["direction"],
                    "duration": params["duration"],
                    "speed": params["speed"],
                    "torque": params["torque"],
                },
                {"step": "motion_stop"},
            ]
        elif intent == "STOP":
            actions = [{"step": "motion_stop"}]
        elif intent == "SET_MODE":
            actions = [{"step": "set_mode", "mode": params["mode"]}]
        elif intent == "EMERGENCY_STOP":
            actions = [{"step": "emergency_stop", "reason": params["reason"]}]
        else:
            actions = [{"step": "clear_emergency_stop", "require_ack": params["require_ack"]}]
        trace = list(state.get("trace", []))
        trace.append("reasoning:plan_compiled")
        return {"action_plan": actions, "trace": trace}
    def _execute_node(self, state: CommandGraphState) -> dict[str, Any]:
        result = self.ros_bridge.execute_validated_command(state["validated_command"])
        trace = list(state.get("trace", []))
        trace.append("execute:hardware_ack")
        return {"execution_result": result, "trace": trace}
    def _audit_node(self, state: CommandGraphState) -> dict[str, Any]:
        command = state["validated_command"]
        result = state["execution_result"]
        context = {
            "uid": state["user_uid"],
            "roles": list(state["user_roles"]),
            "intent": command["intent"],
            "parameters": command["parameters"],
            "result": result,
            "trace": state.get("trace", []),
        }
        self.telemetry.push_log(level="INFO", message="Command executed", context=context)
        trace = list(state.get("trace", []))
        trace.append("audit:logged")
        return {"trace": trace}
    async def execute(self, *, command: dict[str, Any], user: AuthenticatedUser) -> dict[str, Any]:
        state: CommandGraphState = {
            "command": command,
            "user_uid": user.uid,
            "user_roles": user.roles,
            "trace": [],
        }
        return await asyncio.to_thread(self.graph.invoke, state)
@dataclass
class AppComponents:
    auth: FirebaseAuthValidator
    policy: CommandPolicy
    ros_bridge: ROSSafetyBridge
    telemetry: TelemetrySync
    engine: CommandExecutionEngine
    runtime: RuntimeState
    system_monitor: SystemMonitor
    ai_agent: Any = None                  
bearer = HTTPBearer(auto_error=False)
def _normalize_wake_target(raw_target: str) -> str:
    target = str(raw_target).strip().lower()
    if target not in {"aegis", "edith"}:
        raise HTTPException(status_code=400, detail="Invalid wake target. Use 'aegis' or 'edith'.")
    return target
def _dispatch_core_wake(*, target: str, source: str, requested_by: str) -> dict[str, Any]:
    core_base = os.getenv("AEGIS_CORE_CONTROL_URL", "http://127.0.0.1:8000").rstrip("/")
    wake_url = f"{core_base}/api/control/wake"
    timeout = float(os.getenv("AEGIS_CORE_WAKE_TIMEOUT_SECONDS", "10"))
    verify_tls = os.getenv("AEGIS_CORE_VERIFY_TLS", "false").strip().lower() in {"1", "true", "yes", "on"}
    payload = json.dumps(
        {
            "target": target,
            "source": source,
            "requested_by": requested_by,
        }
    ).encode("utf-8")
    request_obj = urllib_request.Request(
        wake_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    ssl_context = None
    if wake_url.startswith("https://") and not verify_tls:
        ssl_context = ssl._create_unverified_context()
    try:
        with urllib_request.urlopen(request_obj, timeout=timeout, context=ssl_context) as response:
            body = response.read().decode("utf-8")
            if not body:
                return {"success": True, "status_code": response.status}
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"success": True, "status_code": response.status, "raw": body}
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=502,
            detail=f"Core wake endpoint HTTP {exc.code}: {detail}",
        ) from exc
    except urllib_error.URLError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Core wake endpoint unreachable: {exc.reason}",
        ) from exc
def _cors_origins() -> list[str]:
    raw = os.getenv("AEGIS_DASHBOARD_ORIGINS", "")
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]
def _build_components() -> AppComponents:
    service_account = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    project_id = os.getenv("FIREBASE_PROJECT_ID")
    node_id = os.getenv("AEGIS_NODE_ID", "aegis-node-1")
    auth = FirebaseAuthValidator(service_account_path=service_account, project_id=project_id)
    policy = CommandPolicy(
        SafetyLimits(
            max_linear_speed=float(os.getenv("AEGIS_MAX_LINEAR_SPEED", "0.8")),
            max_angular_speed=float(os.getenv("AEGIS_MAX_ANGULAR_SPEED", "1.2")),
            max_torque=float(os.getenv("AEGIS_MAX_TORQUE", "60")),
            max_duration=float(os.getenv("AEGIS_MAX_COMMAND_DURATION", "5")),
            min_obstacle_distance=float(os.getenv("AEGIS_MIN_OBSTACLE_DISTANCE", "0.50")),
        )
    )
    ros_bridge = ROSSafetyBridge(
        limits=BridgeLimits(
            max_linear_speed=float(os.getenv("AEGIS_MAX_LINEAR_SPEED", "0.8")),
            max_angular_speed=float(os.getenv("AEGIS_MAX_ANGULAR_SPEED", "1.2")),
            max_torque=float(os.getenv("AEGIS_MAX_TORQUE", "60")),
            min_obstacle_distance=float(os.getenv("AEGIS_MIN_OBSTACLE_DISTANCE", "0.50")),
            command_publish_rate_hz=float(os.getenv("AEGIS_COMMAND_RATE_HZ", "20")),
        )
    )
    telemetry = TelemetrySync(
        node_id=node_id,
        service_account_path=service_account,
        project_id=project_id,
    )
    runtime = RuntimeState(node_id=node_id)
    engine = CommandExecutionEngine(policy=policy, ros_bridge=ros_bridge, telemetry=telemetry)
    event_bus = EventBus()
    system_monitor = SystemMonitor(event_bus)
    enable_monitor = os.getenv("AEGIS_ENABLE_SYSTEM_MONITOR", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if enable_monitor:
        system_monitor.start()
    ai_agent = get_ai_agent()
    return AppComponents(
        auth=auth,
        policy=policy,
        ros_bridge=ros_bridge,
        telemetry=telemetry,
        engine=engine,
        runtime=runtime,
        system_monitor=system_monitor,
        ai_agent=ai_agent,
    )
def _require_roles(*required_roles: str):
    normalized_required = {role.strip().lower() for role in required_roles}
    async def dependency(
        request: Request,
        credentials_obj: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> AuthenticatedUser:
        components: AppComponents = request.app.state.components
        user = components.auth.verify_bearer(credentials_obj)
        if normalized_required and not normalized_required.intersection(user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role one of: {', '.join(sorted(normalized_required))}",
            )
        return user
    return dependency
async def _telemetry_loop(app: FastAPI) -> None:
    components: AppComponents = app.state.components
    interval = float(os.getenv("AEGIS_TELEMETRY_INTERVAL_SECONDS", "2.0"))
    while True:
        try:
            agent_state, tasks = await components.runtime.snapshot()
            sensors = await asyncio.to_thread(components.ros_bridge.get_sensor_snapshot)
            payload = await asyncio.to_thread(
                components.telemetry.build_snapshot,
                agent_state=agent_state,
                sensors=sensors,
                tasks=tasks,
            )
            await asyncio.to_thread(components.telemetry.push_snapshot, payload)
        except Exception:
            logger.exception("telemetry_loop_error")
        await asyncio.sleep(interval)
@asynccontextmanager
async def lifespan(app: FastAPI):
    components = _build_components()
    app.state.components = components
    await components.runtime.mark_online()
    components.telemetry.push_log(level="INFO", message="API gateway started")
    def run_telemetry():
        import time
        interval = float(os.getenv("AEGIS_TELEMETRY_INTERVAL_SECONDS", "5.0"))
        while True:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                agent_state, tasks = loop.run_until_complete(components.runtime.snapshot())
                sensors = loop.run_until_complete(asyncio.to_thread(components.ros_bridge.get_sensor_snapshot))
                payload = loop.run_until_complete(asyncio.to_thread(
                    components.telemetry.build_snapshot,
                    agent_state=agent_state,
                    sensors=sensors,
                    tasks=tasks,
                ))
                loop.run_until_complete(asyncio.to_thread(components.telemetry.push_snapshot, payload))
                loop.close()
            except Exception:
                pass
            time.sleep(interval)
    import threading
    telemetry_thread = threading.Thread(target=run_telemetry, daemon=True)
    telemetry_thread.start()
    app.state.telemetry_thread = telemetry_thread
    try:
        yield
    finally:
        components.telemetry.push_log(level="INFO", message="API gateway stopped")
        components.system_monitor.shutdown()
        components.ros_bridge.shutdown()
app = FastAPI(
    title="AEGIS API Gateway",
    description="Authenticated local API gateway with LangGraph orchestration and ROS2 safety controls",
    version="1.0.0",
    lifespan=lifespan,
)
origins = _cors_origins()
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
@app.exception_handler(PolicyViolation)
async def policy_violation_handler(_: Request, exc: PolicyViolation) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": exc.message, "details": exc.details})
@app.exception_handler(RuntimeError)
async def runtime_error_handler(_: Request, exc: RuntimeError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"error": str(exc)})
@app.get("/healthz")
async def healthz(request: Request) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    context = components.ros_bridge.get_runtime_context()
    return {
        "status": "ok",
        "node_id": components.runtime.node_id,
        "estop_engaged": context["estop_engaged"],
        "obstacle_distance": context["obstacle_distance"],
        "ros_available": context.get("ros_available", False),
        "firebase_auth": components.auth.firebase_enabled,
        "firebase_telemetry": components.telemetry.firebase_enabled,
        "mock_auth_enabled": components.auth.mock_auth_enabled,
    }
@app.get("/v1/me")
async def me(user: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin"))) -> dict[str, Any]:
    return {"uid": user.uid, "email": user.email, "roles": list(user.roles)}
@app.get("/v1/telemetry/latest")
async def telemetry_latest(
    request: Request,
    _: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    payload = await asyncio.to_thread(components.telemetry.pull_latest)
    if payload is None:
        raise HTTPException(status_code=404, detail="Telemetry document not found")
    return payload
@app.get("/v1/commands/examples")
async def command_examples(
    _: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin")),
) -> dict[str, Any]:
    return {
        "examples": [
            {
                "intent": "MOVE",
                "parameters": {"direction": "FORWARD", "duration": 1.5, "speed": 0.4, "torque": 20},
            },
            {"intent": "STOP", "parameters": {"immediate": True}},
            {"intent": "SET_MODE", "parameters": {"mode": "AUTONOMOUS"}},
            {"intent": "EMERGENCY_STOP", "parameters": {"reason": "manual safety stop"}},
            {"intent": "CLEAR_ESTOP", "parameters": {"require_ack": True}},
        ],
        "execution_flow": ["policy_gate", "reasoning", "execute", "audit"],
    }
@app.post("/v1/commands/execute", response_model=CommandResponse)
async def execute_command(
    request: Request,
    command: CommandRequest,
    user: AuthenticatedUser = Depends(_require_roles("operator", "admin")),
) -> CommandResponse:
    components: AppComponents = request.app.state.components
    intent = command.intent.upper()
    await components.runtime.mark_command_started(intent=intent, operator_uid=user.uid)
    try:
        result = await components.engine.execute(command=command.model_dump(), user=user)
        mode = None
        execution = result.get("execution_result", {})
        if command.intent.upper() == "SET_MODE":
            mode = str(command.parameters.get("mode", "")).upper()
        await components.runtime.mark_command_done(success=True, mode=mode)
        return CommandResponse(
            accepted=True,
            trace=result.get("trace", []),
            result=execution,
            executed_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        await components.runtime.mark_command_done(success=False, error=str(exc))
        components.telemetry.push_log(
            level="ERROR",
            message="Command execution failed",
            context={"uid": user.uid, "intent": intent, "error": str(exc)},
        )
        raise
@app.post("/v1/control/wake")
async def control_wake(
    request: Request,
    wake: WakeRequest,
    user: AuthenticatedUser = Depends(_require_roles("operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    target = _normalize_wake_target(wake.target)
    result = await asyncio.to_thread(
        _dispatch_core_wake,
        target=target,
        source=wake.source,
        requested_by=user.uid,
    )
    components.telemetry.push_log(
        level="INFO",
        message="Remote wake dispatched",
        context={
            "uid": user.uid,
            "roles": list(user.roles),
            "target": target,
            "source": wake.source,
            "result": result,
        },
    )
    return {
        "accepted": True,
        "target": target,
        "source": wake.source,
        "requested_by": user.uid,
        "result": result,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
@app.get("/v1/system/stats")
async def get_system_stats(
    request: Request,
    _: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    return components.system_monitor.get_system_stats()
@app.get("/v1/system/defense-status")
async def get_defense_status(
    request: Request,
    _: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    return components.system_monitor.get_defense_status()
@app.get("/v1/system/threats")
async def get_threats(
    request: Request,
    _: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    return {"threats": components.system_monitor.get_threats()}
@app.get("/v1/system/connections")
async def get_connections(
    request: Request,
    _: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    return {"connections": components.system_monitor.get_network_connections()}
@app.get("/v1/system/processes")
async def get_processes(
    request: Request,
    _: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    return {"processes": components.system_monitor.get_process_list()}
@app.get("/v1/system/dl-analytics")
async def get_dl_analytics(
    request: Request,
    _: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    return components.system_monitor.get_dl_defense_analytics()
@app.post("/v1/antivirus/scan")
async def run_antivirus_scan(
    request: Request,
    user: AuthenticatedUser = Depends(_require_roles("operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    result = components.system_monitor.perform_antivirus_scan()
    components.telemetry.push_log(
        level="INFO",
        message="Antivirus scan completed",
        context={"user": user.uid, "result": result},
    )
    return result
class AICommandRequest(BaseModel):
    command: str
    context: dict[str, Any] = {}
@app.post("/v1/ai/command")
async def ai_command(
    request: Request,
    ai_req: AICommandRequest,
    user: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    result = components.ai_agent.process_command(ai_req.command, ai_req.context)
    return result
@app.get("/v1/ai/status")
async def ai_status(
    request: Request,
    user: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    return components.ai_agent.get_status()
@app.get("/v1/ai/brain")
async def ai_brain_status(
    request: Request,
    user: AuthenticatedUser = Depends(_require_roles("viewer", "operator", "admin")),
) -> dict[str, Any]:
    components: AppComponents = request.app.state.components
    return components.ai_agent.brain.get_status()
def run() -> None:
    import uvicorn
    host = os.getenv("AEGIS_API_HOST", "127.0.0.1")
    port = int(os.getenv("AEGIS_API_PORT", "8000"))
    cert_file = os.getenv("AEGIS_SSL_CERT_FILE")
    key_file = os.getenv("AEGIS_SSL_KEY_FILE")
    use_ssl = cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file)
    if not use_ssl:
        print("Running in HTTP mode (no SSL)")
        uvicorn.run(
            "api_gateway:app",
            host=host,
            port=port,
            proxy_headers=True,
            forwarded_allow_ips="*",
        )
    else:
        print(f"Running in HTTPS mode on {host}:{port}")
        uvicorn.run(
            "api_gateway:app",
            host=host,
            port=port,
            ssl_certfile=cert_file,
            ssl_keyfile=key_file,
            proxy_headers=True,
            forwarded_allow_ips="*",
        )
if __name__ == "__main__":
    run()
