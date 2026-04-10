"""
AEGIS Thermal Manager
Monitors system temperature and prevents overheating
Implements thermal throttling and emergency cooling strategies
"""

import asyncio
import logging
import psutil
import threading
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Callable, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ThermalLevel(Enum):
    NORMAL = "normal"
    WARM = "warm"
    HOT = "hot"
    CRITICAL = "critical"


@dataclass
class ThermalThresholds:
    warm_temp: float = 70.0
    hot_temp: float = 80.0
    critical_temp: float = 90.0
    throttling_threshold: float = 85.0
    emergency_threshold: float = 95.0
    check_interval: float = 5.0


class ThermalManager:
    """
    Monitors system temperature and implements cooling strategies.
    Coordinates with other managers to throttle or disable modules.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, thresholds: Optional[ThermalThresholds] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._thresholds = thresholds or ThermalThresholds()
        self._callbacks: List[Callable] = []
        self._emergency_callbacks: List[Callable] = []
        
        self._current_temp: float = 0.0
        self._current_level = ThermalLevel.NORMAL
        self._temperature_history: List[float] = []
        self._max_history = 100
        
        self._cooling_active = False
        self._throttled_modules: set = set()
        
        self._monitor_task: Optional[asyncio.Task] = None
        self._monitoring = False
    
    @property
    def current_temperature(self) -> float:
        return self._current_temp
    
    @property
    def current_level(self) -> ThermalLevel:
        return self._current_level
    
    @property
    def is_cooling_active(self) -> bool:
        return self._cooling_active
    
    def subscribe(self, callback: Callable):
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def subscribe_emergency(self, callback: Callable):
        if callback not in self._emergency_callbacks:
            self._emergency_callbacks.append(callback)
    
    async def start(self):
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("ThermalManager started")
    
    async def stop(self):
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("ThermalManager stopped")
    
    async def _monitor_loop(self):
        while self._monitoring:
            try:
                temp = self._get_temperature()
                if temp is not None:
                    self._current_temp = temp
                    self._temperature_history.append(temp)
                    if len(self._temperature_history) > self._max_history:
                        self._temperature_history.pop(0)
                    
                    await self._evaluate_thermal_state()
                
                await asyncio.sleep(self._thresholds.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Thermal monitor error: {e}")
                await asyncio.sleep(5.0)
    
    def _get_temperature(self) -> Optional[float]:
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    for entry in entries:
                        if entry.current:
                            return entry.current
            return None
        except Exception:
            return None
    
    async def _evaluate_thermal_state(self):
        temp = self._current_temp
        old_level = self._current_level
        
        if temp >= self._thresholds.emergency_threshold:
            self._current_level = ThermalLevel.CRITICAL
            await self._handle_critical()
        elif temp >= self._thresholds.critical_temp:
            self._current_level = ThermalLevel.HOT
            await self._handle_hot()
        elif temp >= self._thresholds.warm_temp:
            self._current_level = ThermalLevel.WARM
            await self._handle_warm()
        else:
            self._current_level = ThermalLevel.NORMAL
            await self._handle_normal()
        
        if self._current_level != old_level:
            logger.info(f"Thermal level changed: {old_level.value} -> {self._current_level.value} ({temp:.1f}°C)")
            
            for callback in self._callbacks:
                try:
                    callback(self._current_level, temp)
                except Exception as e:
                    logger.error(f"Thermal callback error: {e}")
    
    async def _handle_critical(self):
        self._cooling_active = True
        logger.critical(f"CRITICAL TEMPERATURE: {self._current_temp:.1f}°C")
        
        for callback in self._emergency_callbacks:
            try:
                callback(self._current_temp)
            except Exception as e:
                logger.error(f"Emergency callback error: {e}")
    
    async def _handle_hot(self):
        self._cooling_active = True
        logger.warning(f"HIGH TEMPERATURE: {self._current_temp:.1f}°C")
        
        if self._temperature_history[-10:]:
            avg_recent = sum(self._temperature_history[-10:]) / 10
            if avg_recent > self._thresholds.critical_temp:
                logger.warning("Temperature still rising, initiating aggressive cooling")
    
    async def _handle_warm(self):
        if not self._cooling_active:
            logger.info(f"System warming: {self._current_temp:.1f}°C")
    
    async def _handle_normal(self):
        if self._cooling_active:
            logger.info("Temperature normalized, cooling inactive")
            self._cooling_active = False
    
    def get_throttle_recommendations(self) -> List[Dict]:
        temp = self._current_temp
        
        if temp >= self._thresholds.emergency_threshold:
            return [
                {"module": "vision", "action": "disable", "reason": "Critical temp"},
                {"module": "deep_learning", "action": "disable", "reason": "Critical temp"},
                {"module": "health_monitor", "action": "reduce", "reason": "Critical temp"},
                {"module": "livekit", "action": "disable", "reason": "Critical temp"},
            ]
        elif temp >= self._thresholds.critical_temp:
            return [
                {"module": "vision", "action": "throttle", "reason": "High temp"},
                {"module": "deep_learning", "action": "throttle", "reason": "High temp"},
                {"module": "social_agent", "action": "pause", "reason": "High temp"},
            ]
        elif temp >= self._thresholds.hot_temp:
            return [
                {"module": "deep_learning", "action": "reduce", "reason": "Warm"},
                {"module": "vision", "action": "reduce", "reason": "Warm"},
            ]
        
        return []
    
    def get_average_temp(self, last_n: int = 10) -> float:
        if not self._temperature_history:
            return 0.0
        return sum(self._temperature_history[-last_n:]) / min(last_n, len(self._temperature_history))
    
    def get_thermal_trend(self) -> str:
        if len(self._temperature_history) < 5:
            return "insufficient_data"
        
        recent = self._temperature_history[-5:]
        if all(recent[i] < recent[i+1] for i in range(len(recent)-1)):
            return "rising"
        elif all(recent[i] > recent[i+1] for i in range(len(recent)-1)):
            return "falling"
        return "stable"
