import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Showtime")

@dataclass
class StageRecord:
    name: str
    modules: List[str] = field(default_factory=list)
    status: str = "pending"
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    errors: List[str] = field(default_factory=list)
    required: bool = True


class ShowtimeManager:
    def __init__(self, event_bus: Any, core: Any):
        self.event_bus = event_bus
        self.core = core
        self.stages: Dict[str, StageRecord] = {
            "foundation": StageRecord(
                name="foundation",
                modules=[
                    "event_bus",
                    "runtime",
                    "config",
                    "state",
                    "rbac",
                    "audio_calibration",
                    "first_boot"
                ],
            ),
            "core": StageRecord(
                name="core",
                modules=[
                    "health",
                    "governance",
                    "identity",
                    "voice_biometric",
                    "ai",
                    "speech",
                    "vision",
                    "sound_monitor"
                ],
            ),
            "essential": StageRecord(
                name="essential",
                modules=[
                    "spirituality",
                    "homebot",
                    "ui",
                    "voice_interface",
                    "brain",
                    "greeting",
                    "spatial_audio",
                    "task_manager",
                    "window_manager"
                ],
            ),
            "standard": StageRecord(
                name="standard",
                modules=[
                    "system_tray",
                    "social_agent",
                    "hybrid",
                    "usb_watchdog",
                    "remote_desktop",
                    "engagement"
                ],
            ),
            "optional": StageRecord(
                name="optional",
                modules=[
                    "cloud_bridge",
                    "music",
                    "weather",
                    "news"
                ],
                required=False,
            ),
            "lazy": StageRecord(
                name="lazy",
                modules=[
                    "dl_core",
                    "neural_policy",
                    "ml_core",
                    "pattern_recognition",
                    "self_evolution"
                ],
                required=False,
            ),
        }
        self.showtime_started_at: Optional[float] = None
        self.showtime_mode: str = "standby"
        self.stabilization_mode: bool = False
        self.last_health_snapshot: Dict[str, Any] = {}
        self._loop_task: Optional[asyncio.Task] = None
        self.event_bus.subscribe("health_update", self._on_health_update)
        self.event_bus.subscribe("system_alert", self._on_system_alert)
        self.event_bus.subscribe("restart_command", self._on_restart_command)

    def start_lineup(self):
        logger.info("Showtime Manager initializing startup lineup...")
        now = time.time()
        for stage in self.stages.values():
            stage.status = "pending"
            stage.started_at = None
            stage.completed_at = None
            stage.errors = []
        self.showtime_mode = "lineup"
        self.event_bus.publish("system_lineup", self.get_lineup_status())

    def complete_stage(self, stage_name: str, errors: Optional[List[str]] = None):
        stage = self.stages.get(stage_name)
        if not stage:
            logger.warning(f"Unknown lineup stage: {stage_name}")
            return
        stage.started_at = stage.started_at or time.time()
        stage.completed_at = time.time()
        stage.status = "completed" if not errors else "completed_with_errors"
        if errors:
            stage.errors.extend(errors)
        logger.info(f"Lineup stage complete: {stage_name} ({stage.status})")
        self.event_bus.publish("system_lineup", self.get_lineup_status())
        if self._all_stages_complete():
            self.enter_showtime()

    def _all_stages_complete(self) -> bool:
        return all(
            stage.status.startswith("completed") or not stage.required
            for stage in self.stages.values()
        )

    def enter_showtime(self):
        if self.showtime_mode == "showtime":
            return
        self.showtime_started_at = time.time()
        self.showtime_mode = "showtime"
        logger.info("System entering showtime mode for 24/7 runtime.")
        self.event_bus.publish("showtime_started", self.get_showtime_status())
        if not self._loop_task or self._loop_task.done():
            self._loop_task = asyncio.create_task(self._showtime_loop())

    def get_lineup_status(self) -> Dict[str, Any]:
        return {
            "mode": self.showtime_mode,
            "stages": {
                name: {
                    "status": stage.status,
                    "started_at": stage.started_at,
                    "completed_at": stage.completed_at,
                    "errors": stage.errors,
                    "modules": stage.modules,
                }
                for name, stage in self.stages.items()
            },
            "timestamp": time.time(),
        }

    def get_showtime_status(self) -> Dict[str, Any]:
        uptime = None
        if self.showtime_started_at:
            uptime = time.time() - self.showtime_started_at
        return {
            "mode": self.showtime_mode,
            "uptime_seconds": uptime,
            "stabilization_mode": self.stabilization_mode,
            "health_snapshot": self.last_health_snapshot,
            "timestamp": time.time(),
        }

    def _on_health_update(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        self.last_health_snapshot = data
        if self.showtime_mode == "showtime" and self._should_stabilize(data):
            self._enter_stabilization_mode(data)
        elif self.stabilization_mode and not self._should_stabilize(data):
            self._exit_stabilization_mode(data)

    def _on_system_alert(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        if data.get("type") in ("health", "critical", "stability"):
            self._enter_stabilization_mode(data)

    def _on_restart_command(self, data: Any):
        logger.info("Received restart command from showtime manager.")
        self.showtime_mode = "restarting"

    def _should_stabilize(self, health: Dict[str, Any]) -> bool:
        cpu = health.get("cpu", 0)
        memory = health.get("memory", 0)
        disk = health.get("disk", 0)
        state = health.get("state", "healthy")
        return (
            cpu > 80 or
            memory > 86 or
            disk > 90 or
            state in ["warning", "critical"]
        )

    def _enter_stabilization_mode(self, health: Dict[str, Any]):
        if self.stabilization_mode:
            return
        self.stabilization_mode = True
        logger.warning("Showtime stabilization engaged.")
        self.event_bus.publish("system_stabilization", {"status": "engaged", "health": health})
        self._apply_runtime_reductions()

    def _exit_stabilization_mode(self, health: Dict[str, Any]):
        if not self.stabilization_mode:
            return
        self.stabilization_mode = False
        logger.info("Showtime stabilization disengaged.")
        self.event_bus.publish("system_stabilization", {"status": "disengaged", "health": health})
        self._restore_normal_runtime()

    def _apply_runtime_reductions(self):
        logger.info("Applying runtime load reduction to protect system health.")
        if hasattr(self.core, "vision_enabled"):
            self.core.vision_enabled = False
        if hasattr(self.core, "voice_enabled"):
            self.core.voice_enabled = False
        if hasattr(self.core, "social_agent") and self.core.social_agent:
            try:
                self.core.social_agent.pause()
            except Exception:
                pass
        if hasattr(self.core, "dl_core") and self.core.dl_core:
            try:
                self.core.dl_core.pause_learning()
            except Exception:
                pass
        if hasattr(self.core, "ml_core") and self.core.ml_core:
            try:
                self.core.ml_core.pause_learning()
            except Exception:
                pass

    def _restore_normal_runtime(self):
        logger.info("Restoring normal runtime behavior after stabilization.")
        if hasattr(self.core, "vision_enabled"):
            self.core.vision_enabled = True
        if hasattr(self.core, "voice_enabled"):
            self.core.voice_enabled = True
        if hasattr(self.core, "social_agent") and self.core.social_agent:
            try:
                self.core.social_agent.resume()
            except Exception:
                pass
        if hasattr(self.core, "dl_core") and self.core.dl_core:
            try:
                self.core.dl_core.resume_learning()
            except Exception:
                pass
        if hasattr(self.core, "ml_core") and self.core.ml_core:
            try:
                self.core.ml_core.resume_learning()
            except Exception:
                pass

    async def _showtime_loop(self):
        while self.showtime_mode == "showtime":
            try:
                if self.core and hasattr(self.core, "runtime"):
                    stats = self.core.runtime.get_resource_usage()
                    self.last_health_snapshot.update(stats)
                    if self._should_stabilize(self.last_health_snapshot):
                        self._enter_stabilization_mode(self.last_health_snapshot)
                    elif self.stabilization_mode:
                        self._exit_stabilization_mode(self.last_health_snapshot)
                    self.event_bus.publish("showtime_status", self.get_showtime_status())
                await asyncio.sleep(12)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Showtime loop error: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        self.showtime_mode = "stopped"
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        logger.info("Showtime Manager stopped.")
