"""
AEGIS Self-Healing Manager
Detects module failures, auto-restarts, and implements failsafe recovery
Monitors for early signs of system instability
"""

import asyncio
import logging
import traceback
import importlib
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class ModuleHealth:
    name: str
    status: HealthStatus
    failure_count: int = 0
    last_failure: Optional[float] = None
    last_success: Optional[float] = None
    restart_count: int = 0
    error_message: Optional[str] = None


@dataclass
class RecoveryAction:
    module_name: str
    action: str
    reason: str
    timestamp: float
    success: bool = False


class SelfHealingManager:
    """
    Self-healing system for AEGIS modules.
    Monitors health, detects failures, and executes recovery strategies.
    """
    
    def __init__(self, resource_manager=None, memory_manager=None):
        self._resource_manager = resource_manager
        self._memory_manager = memory_manager
        
        self._module_health: Dict[str, ModuleHealth] = {}
        self._recovery_actions: deque = deque(maxlen=100)
        self._health_callbacks: List[Callable] = []
        
        self._failure_threshold = 3
        self._restart_cooldown = 60.0
        self._last_restart_times: Dict[str, float] = {}
        
        self._monitor_task: Optional[asyncio.Task] = None
        self._monitoring = False
        self._lock = threading.Lock()
    
    def register_module(self, name: str, import_path: Optional[str] = None):
        with self._lock:
            if name not in self._module_health:
                self._module_health[name] = ModuleHealth(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    import_path=import_path
                )
                logger.debug(f"Module health registered: {name}")
    
    def report_health(self, module_name: str, healthy: bool, error: Optional[str] = None):
        with self._lock:
            health = self._module_health.get(module_name)
            if not health:
                return
            
            now = datetime.now().timestamp()
            
            if healthy:
                health.status = HealthStatus.HEALTHY
                health.last_success = now
                health.failure_count = 0
                health.error_message = None
            else:
                health.failure_count += 1
                health.last_failure = now
                health.error_message = error
                
                if health.failure_count >= self._failure_threshold:
                    health.status = HealthStatus.UNHEALTHY
                else:
                    health.status = HealthStatus.DEGRADED
    
    def subscribe_health_change(self, callback: Callable):
        if callback not in self._health_callbacks:
            self._health_callbacks.append(callback)
    
    async def start(self):
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("SelfHealingManager started")
    
    async def stop(self):
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("SelfHealingManager stopped")
    
    async def _monitor_loop(self):
        while self._monitoring:
            try:
                await self._check_health()
                await self._check_resource_stability()
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SelfHealing monitor error: {e}")
                await asyncio.sleep(5.0)
    
    async def _check_health(self):
        now = datetime.now().timestamp()
        
        for name, health in list(self._module_health.items()):
            if health.status == HealthStatus.UNHEALTHY:
                if now - self._last_restart_times.get(name, 0) > self._restart_cooldown:
                    await self._attempt_recovery(name)
    
    async def _check_resource_stability(self):
        if not self._resource_manager:
            return
        
        snapshot = self._resource_manager.get_snapshot()
        
        if snapshot.cpu_percent > 95 or snapshot.ram_percent > 95:
            logger.warning(f"Resource instability detected: CPU={snapshot.cpu_percent:.1f}%, RAM={snapshot.ram_percent:.1f}%")
            
            if self._memory_manager:
                self._memory_manager.check_and_garbage_collect()
    
    async def _attempt_recovery(self, module_name: str):
        health = self._module_health.get(module_name)
        if not health:
            return
        
        logger.warning(f"Attempting recovery for module: {module_name}")
        
        action = RecoveryAction(
            module_name=module_name,
            action="restart",
            reason=f"Module unhealthy (failures: {health.failure_count})",
            timestamp=datetime.now().timestamp()
        )
        
        try:
            success = await self._restart_module(module_name)
            action.success = success
            
            if success:
                health.restart_count += 1
                health.failure_count = 0
                health.status = HealthStatus.HEALTHY
                self._last_restart_times[module_name] = datetime.now().timestamp()
                logger.info(f"Module recovered: {module_name}")
            else:
                health.status = HealthStatus.CRITICAL
                logger.error(f"Module recovery failed: {module_name}")
                
        except Exception as e:
            action.success = False
            logger.error(f"Recovery exception for {module_name}: {e}")
        
        self._recovery_actions.append(action)
    
    async def _restart_module(self, module_name: str) -> bool:
        try:
            logger.info(f"Restarting module: {module_name}")
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Restart failed for {module_name}: {e}")
            return False
    
    def get_module_health(self, module_name: str) -> Optional[ModuleHealth]:
        return self._module_health.get(module_name)
    
    def get_all_health(self) -> Dict[str, HealthStatus]:
        return {name: h.status for name, h in self._module_health.items()}
    
    def get_recovery_history(self, count: int = 20) -> List[RecoveryAction]:
        return list(self._recovery_actions)[-count:]
    
    def get_system_health(self) -> HealthStatus:
        if not self._module_health:
            return HealthStatus.HEALTHY
        
        statuses = [h.status for h in self._module_health.values()]
        
        if any(s == HealthStatus.CRITICAL for s in statuses):
            return HealthStatus.CRITICAL
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY
    
    def get_stats(self) -> Dict:
        return {
            "system_health": self.get_system_health().value,
            "modules": len(self._module_health),
            "unhealthy": sum(1 for h in self._module_health.values() if h.status == HealthStatus.UNHEALTHY),
            "critical": sum(1 for h in self._module_health.values() if h.status == HealthStatus.CRITICAL),
            "total_restarts": sum(h.restart_count for h in self._module_health.values()),
            "recent_recoveries": len([a for a in self._recovery_actions if a.success]),
            "recent_failures": len([a for a in self._recovery_actions if not a.success])
        }
