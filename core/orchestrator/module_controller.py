"""
SATURDAY Module Controller
Manages module lifecycle with ducking, suspension, and lazy loading
Optimizes resources by pausing/idling unused modules
"""

import asyncio
import logging
import time
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional, Any, Set
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class ModuleState(Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    RUNNING = "running"
    DUCKED = "ducked"
    SUSPENDED = "suspended"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class ModuleControllerSpec:
    name: str
    priority: int = 5
    idle_timeout: float = 300.0
    ducking_priority: int = 5
    can_hibernate: bool = True
    can_unload: bool = False
    exclusive_resources: List[str] = field(default_factory=list)
    on_activate: Optional[Callable] = None
    on_deactivate: Optional[Callable] = None
    on_hibernate: Optional[Callable] = None
    on_wake: Optional[Callable] = None


class ModuleController:
    """
    Central controller for module lifecycle management.
    Implements ducking, suspension, and lazy loading strategies.
    """
    
    def __init__(self, resource_manager=None, mode_manager=None):
        self._resource_manager = resource_manager
        self._mode_manager = mode_manager
        self._modules: Dict[str, ModuleControllerSpec] = {}
        self._module_states: Dict[str, ModuleState] = {}
        self._module_instances: Dict[str, Any] = {}
        self._module_last_activity: Dict[str, float] = {}
        self._module_activity_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._idle_callbacks: List[Callable] = []
        self._resource_locks: Dict[str, str] = {}
        
        self._monitor_task: Optional[asyncio.Task] = None
        self._monitoring = False
        self._lock = threading.RLock()
        
        self._ducked_modules: Set[str] = set()
        self._suspended_modules: Set[str] = set()
    
    def register_module(self, spec: ModuleControllerSpec):
        self._modules[spec.name] = spec
        self._module_states[spec.name] = ModuleState.UNLOADED
        self._module_last_activity[spec.name] = time.time()
        logger.debug(f"Registered module controller: {spec.name}")
    
    def register_modules(self, specs: List[ModuleControllerSpec]):
        for spec in specs:
            self.register_module(spec)
    
    def get_state(self, module_name: str) -> ModuleState:
        return self._module_states.get(module_name, ModuleState.UNLOADED)
    
    def is_active(self, module_name: str) -> bool:
        state = self.get_state(module_name)
        return state == ModuleState.RUNNING or state == ModuleState.DUCKED
    
    def register_activity(self, module_name: str):
        with self._lock:
            self._module_last_activity[module_name] = time.time()
            if self._module_states.get(module_name) == ModuleState.DUCKED:
                self._wake_module(module_name)
    
    def subscribe_activity(self, module_name: str, callback: Callable):
        if module_name not in self._activity_callbacks:
            self._activity_callbacks[module_name] = []
        self._activity_callbacks[module_name].append(callback)
    
    def subscribe_idle(self, callback: Callable):
        if callback not in self._idle_callbacks:
            self._idle_callbacks.append(callback)
    
    async def start(self):
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("ModuleController started")
    
    async def stop(self):
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("ModuleController stopped")
    
    async def _monitor_loop(self):
        check_interval = 30.0
        
        while self._monitoring:
            try:
                await self._check_idle_modules()
                await self._check_resource_pressure()
                await asyncio.sleep(check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"ModuleController monitor error: {e}")
                await asyncio.sleep(5.0)
    
    async def _check_idle_modules(self):
        now = time.time()
        
        for name, spec in self._modules.items():
            state = self._module_states.get(name)
            if state not in (ModuleState.RUNNING, ModuleState.DUCKED):
                continue
            
            idle_time = now - self._module_last_activity.get(name, now)
            
            if idle_time >= spec.idle_timeout:
                if state == ModuleState.RUNNING:
                    await self._duck_module(name)
                elif spec.can_hibernate:
                    await self._hibernate_module(name)
    
    async def _check_resource_pressure(self):
        if not self._resource_manager:
            return
        
        snapshot = self._resource_manager.get_snapshot()
        
        if snapshot.ram_percent >= 90 or snapshot.cpu_percent >= 90:
            await self._aggressive_ducking()
    
    async def _aggressive_ducking(self):
        priority_threshold = 3
        
        ducked = 0
        for name, spec in sorted(self._modules.items(), key=lambda x: x[1].priority):
            if spec.priority < priority_threshold:
                continue
            state = self._module_states.get(name)
            if state == ModuleState.RUNNING:
                await self._duck_module(name)
                ducked += 1
                if ducked >= 3:
                    break
    
    async def _duck_module(self, module_name: str):
        spec = self._modules.get(module_name)
        if not spec:
            return
        
        state = self._module_states.get(module_name)
        if state == ModuleState.DUCKED:
            return
        
        logger.info(f"Ducking module: {module_name}")
        
        self._module_states[module_name] = ModuleState.DUCKED
        self._ducked_modules.add(module_name)
        
        instance = self._module_instances.get(module_name)
        if instance and spec.on_deactivate:
            try:
                spec.on_deactivate(instance)
            except Exception as e:
                logger.error(f"Module {module_name} duck error: {e}")
        
        for callback in self._idle_callbacks:
            try:
                callback(module_name, "ducked")
            except Exception as e:
                logger.error(f"Idle callback error: {e}")
    
    async def _hibernate_module(self, module_name: str):
        spec = self._modules.get(module_name)
        if not spec or not spec.can_hibernate:
            return
        
        logger.info(f"Hibernating module: {module_name}")
        
        instance = self._module_instances.get(module_name)
        if instance and spec.on_hibernate:
            try:
                spec.on_hibernate(instance)
            except Exception as e:
                logger.error(f"Module {module_name} hibernate error: {e}")
        
        self._module_states[module_name] = ModuleState.SUSPENDED
        self._suspended_modules.add(module_name)
        self._module_instances.pop(module_name, None)
        
        for callback in self._idle_callbacks:
            try:
                callback(module_name, "hibernated")
            except Exception as e:
                logger.error(f"Idle callback error: {e}")
    
    async def _wake_module(self, module_name: str):
        spec = self._modules.get(module_name)
        if not spec:
            return
        
        state = self._module_states.get(module_name)
        
        if state == ModuleState.DUCKED:
            logger.info(f"Waking module: {module_name}")
            
            if spec.on_wake:
                instance = self._module_instances.get(module_name)
                if instance:
                    try:
                        spec.on_wake(instance)
                    except Exception as e:
                        logger.error(f"Module {module_name} wake error: {e}")
            
            self._module_states[module_name] = ModuleState.RUNNING
            self._ducked_modules.discard(module_name)
        
        elif state == ModuleState.SUSPENDED:
            logger.info(f"Resuming hibernated module: {module_name}")
            self._module_states[module_name] = ModuleState.RUNNING
            self._suspended_modules.discard(module_name)
        
        self._module_last_activity[module_name] = time.time()
    
    def set_module_instance(self, module_name: str, instance: Any):
        with self._lock:
            self._module_instances[module_name] = instance
            if self._module_states.get(module_name) == ModuleState.UNLOADED:
                self._module_states[module_name] = ModuleState.RUNNING
    
    def force_state(self, module_name: str, state: ModuleState):
        self._module_states[module_name] = state
        logger.info(f"Module {module_name} forced to {state.value}")
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_modules": len(self._modules),
            "running": sum(1 for s in self._module_states.values() if s == ModuleState.RUNNING),
            "ducked": len(self._ducked_modules),
            "suspended": len(self._suspended_modules),
            "unloaded": sum(1 for s in self._module_states.values() if s == ModuleState.UNLOADED)
        }
