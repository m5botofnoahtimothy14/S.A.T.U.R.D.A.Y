"""
SATURDAY Mode Manager
Handles power/performance modes: LOW_POWER, BALANCED, PERFORMANCE
Dynamically adjusts system behavior based on mode and resource state
"""

import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional, Set
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)


class SystemMode(Enum):
    LOW_POWER = "low_power"
    BALANCED = "balanced"
    PERFORMANCE = "performance"
    EMERGENCY = "emergency"


@dataclass
class ModeProfile:
    name: SystemMode
    cpu_limit_percent: float = 100.0
    max_threads: int = 8
    sampling_interval: float = 5.0
    enable_ducking: bool = True
    enable_lazy_loading: bool = True
    max_concurrent_inference: int = 2
    enable_deep_sleep: bool = False
    memory_threshold_percent: float = 90.0
    temperature_threshold: float = 85.0
    auto_throttle: bool = True
    disable_optional_modules: List[str] = field(default_factory=list)


class ModeManager:
    """
    Manages system power/performance modes.
    Automatically adjusts based on resource state and battery.
    """
    
    MODE_PROFILES = {
        SystemMode.LOW_POWER: ModeProfile(
            name=SystemMode.LOW_POWER,
            cpu_limit_percent=50.0,
            max_threads=2,
            sampling_interval=10.0,
            enable_ducking=True,
            enable_lazy_loading=True,
            max_concurrent_inference=1,
            enable_deep_sleep=True,
            memory_threshold_percent=70.0,
            temperature_threshold=75.0,
            disable_optional_modules=["vision", "social_agent", "livekit"]
        ),
        SystemMode.BALANCED: ModeProfile(
            name=SystemMode.BALANCED,
            cpu_limit_percent=75.0,
            max_threads=4,
            sampling_interval=5.0,
            enable_ducking=True,
            enable_lazy_loading=True,
            max_concurrent_inference=2,
            enable_deep_sleep=False,
            memory_threshold_percent=85.0,
            temperature_threshold=85.0,
            disable_optional_modules=["social_agent"]
        ),
        SystemMode.PERFORMANCE: ModeProfile(
            name=SystemMode.PERFORMANCE,
            cpu_limit_percent=100.0,
            max_threads=8,
            sampling_interval=1.0,
            enable_ducking=False,
            enable_lazy_loading=False,
            max_concurrent_inference=4,
            enable_deep_sleep=False,
            memory_threshold_percent=95.0,
            temperature_threshold=95.0,
            disable_optional_modules=[]
        ),
        SystemMode.EMERGENCY: ModeProfile(
            name=SystemMode.EMERGENCY,
            cpu_limit_percent=30.0,
            max_threads=1,
            sampling_interval=15.0,
            enable_ducking=True,
            enable_lazy_loading=True,
            max_concurrent_inference=1,
            enable_deep_sleep=True,
            memory_threshold_percent=50.0,
            temperature_threshold=70.0,
            disable_optional_modules=["vision", "social_agent", "livekit", "health_monitor", "deep_learning"]
        )
    }
    
    def __init__(self, resource_manager=None):
        self._resource_manager = resource_manager
        self._current_mode = SystemMode.BALANCED
        self._profile = self.MODE_PROFILES[self._current_mode]
        self._target_mode = None
        self._mode_change_callbacks: List[Callable] = []
        self._lock = threading.RLock()
        self._last_mode_change = datetime.min
        self._mode_change_cooldown = timedelta(seconds=30)
        self._is_on_battery = False
        self._battery_threshold = 20.0
        self._emergency_triggers: Set[str] = set()
        
        self._monitor_task: Optional[asyncio.Task] = None
        self._monitoring = False
    
    @property
    def current_mode(self) -> SystemMode:
        return self._current_mode
    
    @property
    def profile(self) -> ModeProfile:
        return self._profile
    
    def subscribe_mode_change(self, callback: Callable):
        if callback not in self._mode_change_callbacks:
            self._mode_change_callbacks.append(callback)
    
    def unsubscribe_mode_change(self, callback: Callable):
        if callback in self._mode_change_callbacks:
            self._mode_change_callbacks.remove(callback)
    
    async def start(self):
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"ModeManager started in {self._current_mode.value} mode")
    
    async def stop(self):
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_loop(self):
        while self._monitoring:
            try:
                await self._evaluate_and_adjust()
                await asyncio.sleep(self._profile.sampling_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"ModeManager monitor error: {e}")
                await asyncio.sleep(5.0)
    
    async def _evaluate_and_adjust(self):
        if self._resource_manager:
            snapshot = self._resource_manager.get_snapshot()
            
            self._emergency_triggers.clear()
            
            if snapshot.cpu_percent >= 95:
                self._emergency_triggers.add("cpu_critical")
            if snapshot.ram_percent >= 95:
                self._emergency_triggers.add("ram_critical")
            if snapshot.temperature and snapshot.temperature >= 95:
                self._emergency_triggers.add("temp_critical")
            
            self._is_on_battery = self._resource_manager.is_on_battery()
            
            battery = self._resource_manager.is_on_battery()
            if battery:
                battery_info = self._resource_manager.is_on_battery()
                if battery_info and hasattr(battery_info, 'percent'):
                    if battery_info.percent < self._battery_threshold:
                        self._emergency_triggers.add("low_battery")
            
            await self._determine_mode()
    
    async def _determine_mode(self):
        target = self._current_mode
        
        if self._emergency_triggers:
            target = SystemMode.EMERGENCY
            logger.warning(f"Emergency mode triggered: {self._emergency_triggers}")
        elif self._is_on_battery:
            target = SystemMode.LOW_POWER
        else:
            snapshot = self._resource_manager.get_snapshot() if self._resource_manager else None
            if snapshot:
                if snapshot.cpu_percent < 40 and snapshot.ram_percent < 60:
                    target = SystemMode.PERFORMANCE
                elif snapshot.cpu_percent < 70 and snapshot.ram_percent < 75:
                    target = SystemMode.BALANCED
                else:
                    target = SystemMode.LOW_POWER
        
        if target != self._current_mode:
            await self.set_mode(target, reason="auto")
    
    def set_mode(self, mode: SystemMode, reason: str = "manual") -> bool:
        with self._lock:
            if mode == self._current_mode:
                return True
            
            now = datetime.now()
            if now - self._last_mode_change < self._mode_change_cooldown and reason == "auto":
                logger.debug(f"Mode change cooldown active, skipping")
                return False
            
            old_mode = self._current_mode
            self._current_mode = mode
            self._profile = self.MODE_PROFILES[mode]
            self._last_mode_change = now
            
            logger.info(f"Mode changed: {old_mode.value} -> {mode.value} ({reason})")
            
            for callback in self._mode_change_callbacks:
                try:
                    callback(old_mode, mode, reason)
                except Exception as e:
                    logger.error(f"Mode change callback error: {e}")
            
            return True
    
    def get_ducking_list(self) -> List[str]:
        return self._profile.disable_optional_modules
    
    def should_enable_feature(self, feature: str) -> bool:
        return feature not in self._profile.disable_optional_modules
    
    def get_sampling_interval(self) -> float:
        return self._profile.sampling_interval
    
    def get_max_threads(self) -> int:
        return self._profile.max_threads
    
    def should_throttle(self) -> bool:
        return self._profile.auto_throttle and self._current_mode != SystemMode.PERFORMANCE
