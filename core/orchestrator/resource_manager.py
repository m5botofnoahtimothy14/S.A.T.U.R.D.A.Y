"""
SATURDAY Resource Manager
Monitors CPU, RAM, Disk I/O, and System Temperature
Provides real-time resource metrics and alerts
"""

import psutil
import time
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)


class ResourceLevel(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ResourceType(Enum):
    CPU = "cpu"
    RAM = "ram"
    DISK = "disk"
    TEMPERATURE = "temperature"


@dataclass
class ResourceThresholds:
    cpu_warning: float = 70.0
    cpu_critical: float = 90.0
    ram_warning: float = 75.0
    ram_critical: float = 90.0
    disk_warning: float = 80.0
    disk_critical: float = 95.0
    temp_warning: float = 80.0
    temp_critical: float = 95.0
    sampling_interval: float = 1.0


@dataclass
class ResourceSnapshot:
    timestamp: float
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    ram_total_gb: float
    disk_read_mb: float
    disk_write_mb: float
    temperature: Optional[float] = None
    
    @property
    def cpu_level(self) -> ResourceLevel:
        if self.cpu_percent >= 90:
            return ResourceLevel.CRITICAL
        elif self.cpu_percent >= 70:
            return ResourceLevel.HIGH
        elif self.cpu_percent >= 50:
            return ResourceLevel.NORMAL
        return ResourceLevel.LOW
    
    @property
    def ram_level(self) -> ResourceLevel:
        if self.ram_percent >= 90:
            return ResourceLevel.CRITICAL
        elif self.ram_percent >= 75:
            return ResourceLevel.HIGH
        elif self.ram_percent >= 50:
            return ResourceLevel.NORMAL
        return ResourceLevel.LOW


@dataclass
class ResourceAlert:
    timestamp: float
    resource_type: ResourceType
    level: ResourceLevel
    value: float
    threshold: float
    message: str


class ResourceManager:
    """
    Central resource monitoring system for SATURDAY.
    Tracks CPU, RAM, Disk I/O, and Temperature.
    Maintains history and triggers alerts.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, thresholds: Optional[ResourceThresholds] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self._initialized = True
        self._thresholds = thresholds or ResourceThresholds()
        self._callbacks: Dict[ResourceType, List[Callable]] = {
            rt: [] for rt in ResourceType
        }
        self._alert_callbacks: List[Callable] = []
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        self._history: deque = deque(maxlen=300)
        self._alerts: deque = deque(maxlen=100)
        
        self._last_disk_io = psutil.disk_io_counters()
        self._last_check_time = time.time()
        
        self._onBattery = psutil.sensors_battery().power_plugged is False if psutil.sensors_battery() else False
    
    @property
    def thresholds(self) -> ResourceThresholds:
        return self._thresholds
    
    @thresholds.setter
    def thresholds(self, value: ResourceThresholds):
        self._thresholds = value
    
    def subscribe(self, resource_type: ResourceType, callback: Callable):
        if callback not in self._callbacks[resource_type]:
            self._callbacks[resource_type].append(callback)
    
    def unsubscribe(self, resource_type: ResourceType, callback: Callable):
        if callback in self._callbacks[resource_type]:
            self._callbacks[resource_type].remove(callback)
    
    def subscribe_alerts(self, callback: Callable):
        if callback not in self._alert_callbacks:
            self._alert_callbacks.append(callback)
    
    def get_snapshot(self) -> ResourceSnapshot:
        current_time = time.time()
        
        cpu_percent = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        
        disk_io = psutil.disk_io_counters()
        time_delta = current_time - self._last_check_time
        
        if self._last_disk_io and time_delta > 0:
            read_bytes = disk_io.read_bytes - self._last_disk_io.read_bytes
            write_bytes = disk_io.write_bytes - self._last_disk_io.write_bytes
            disk_read_mb = (read_bytes / (1024 * 1024)) / time_delta
            disk_write_mb = (write_bytes / (1024 * 1024)) / time_delta
        else:
            disk_read_mb = disk_write_mb = 0.0
        
        self._last_disk_io = disk_io
        self._last_check_time = current_time
        
        temperature = self._get_temperature()
        
        snapshot = ResourceSnapshot(
            timestamp=current_time,
            cpu_percent=cpu_percent,
            ram_percent=ram.percent,
            ram_used_gb=ram.used / (1024 ** 3),
            ram_total_gb=ram.total / (1024 ** 3),
            disk_read_mb=disk_read_mb,
            disk_write_mb=disk_write_mb,
            temperature=temperature
        )
        
        self._history.append(snapshot)
        self._check_thresholds(snapshot)
        
        return snapshot
    
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
    
    def _check_thresholds(self, snapshot: ResourceSnapshot):
        alerts = []
        
        if snapshot.cpu_percent >= self._thresholds.cpu_critical:
            level = ResourceLevel.CRITICAL
        elif snapshot.cpu_percent >= self._thresholds.cpu_warning:
            level = ResourceLevel.HIGH
        else:
            return
        
        if level == ResourceLevel.CRITICAL:
            alert = ResourceAlert(
                timestamp=snapshot.timestamp,
                resource_type=ResourceType.CPU,
                level=level,
                value=snapshot.cpu_percent,
                threshold=self._thresholds.cpu_critical,
                message=f"CPU critical: {snapshot.cpu_percent:.1f}%"
            )
            alerts.append(alert)
        elif level == ResourceLevel.HIGH:
            alert = ResourceAlert(
                timestamp=snapshot.timestamp,
                resource_type=ResourceType.CPU,
                level=level,
                value=snapshot.cpu_percent,
                threshold=self._thresholds.cpu_warning,
                message=f"CPU high: {snapshot.cpu_percent:.1f}%"
            )
            alerts.append(alert)
        
        if snapshot.ram_percent >= self._thresholds.ram_critical:
            alerts.append(ResourceAlert(
                timestamp=snapshot.timestamp,
                resource_type=ResourceType.RAM,
                level=ResourceLevel.CRITICAL,
                value=snapshot.ram_percent,
                threshold=self._thresholds.ram_critical,
                message=f"RAM critical: {snapshot.ram_percent:.1f}%"
            ))
        elif snapshot.ram_percent >= self._thresholds.ram_warning:
            alerts.append(ResourceAlert(
                timestamp=snapshot.timestamp,
                resource_type=ResourceType.RAM,
                level=ResourceLevel.HIGH,
                value=snapshot.ram_percent,
                threshold=self._thresholds.ram_warning,
                message=f"RAM high: {snapshot.ram_percent:.1f}%"
            ))
        
        if snapshot.temperature and snapshot.temperature >= self._thresholds.temp_critical:
            alerts.append(ResourceAlert(
                timestamp=snapshot.timestamp,
                resource_type=ResourceType.TEMPERATURE,
                level=ResourceLevel.CRITICAL,
                value=snapshot.temperature,
                threshold=self._thresholds.temp_critical,
                message=f"Temperature critical: {snapshot.temperature:.1f}°C"
            ))
        
        for alert in alerts:
            self._alerts.append(alert)
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Alert callback error: {e}")
    
    def start_monitoring(self):
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ResourceMonitor"
        )
        self._monitor_thread.start()
        logger.info("Resource monitoring started")
    
    def stop_monitoring(self):
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("Resource monitoring stopped")
    
    def _monitor_loop(self):
        while self._monitoring:
            try:
                snapshot = self.get_snapshot()
                
                for callback in self._callbacks[ResourceType.CPU]:
                    try:
                        callback(ResourceType.CPU, snapshot.cpu_percent, snapshot.cpu_level)
                    except Exception as e:
                        logger.error(f"CPU callback error: {e}")
                
                for callback in self._callbacks[ResourceType.RAM]:
                    try:
                        callback(ResourceType.RAM, snapshot.ram_percent, snapshot.ram_level)
                    except Exception as e:
                        logger.error(f"RAM callback error: {e}")
                
                if snapshot.temperature:
                    for callback in self._callbacks[ResourceType.TEMPERATURE]:
                        try:
                            callback(ResourceType.TEMPERATURE, snapshot.temperature, None)
                        except Exception as e:
                            logger.error(f"Temperature callback error: {e}")
                
                time.sleep(self._thresholds.sampling_interval)
                
            except Exception as e:
                logger.error(f"Resource monitor error: {e}")
                time.sleep(1.0)
    
    def get_average_usage(self, seconds: int = 60) -> Dict[str, float]:
        cutoff = time.time() - seconds
        relevant = [s for s in self._history if s.timestamp >= cutoff]
        
        if not relevant:
            return {"cpu": 0.0, "ram": 0.0, "disk_read": 0.0, "disk_write": 0.0}
        
        return {
            "cpu": sum(s.cpu_percent for s in relevant) / len(relevant),
            "ram": sum(s.ram_percent for s in relevant) / len(relevant),
            "disk_read": sum(s.disk_read_mb for s in relevant) / len(relevant),
            "disk_write": sum(s.disk_write_mb for s in relevant) / len(relevant)
        }
    
    def get_recent_alerts(self, count: int = 10) -> List[ResourceAlert]:
        return list(self._alerts)[-count:]
    
    def is_on_battery(self) -> bool:
        try:
            battery = psutil.sensors_battery()
            return battery.power_plugged is False if battery else False
        except Exception:
            return False
    
    def get_cpu_count(self) -> int:
        return psutil.cpu_count()
    
    def get_cpu_count_logical(self) -> int:
        return psutil.cpu_count(logical=True)
