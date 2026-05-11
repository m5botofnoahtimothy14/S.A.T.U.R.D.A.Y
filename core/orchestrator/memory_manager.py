"""
SATURDAY Memory Manager
Manages memory allocation, prevents leaks, and implements caching strategies
Handles model loading/unloading and memory optimization
"""

import gc
import logging
import threading
import psutil
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Callable, Optional, Any
from collections import deque
from datetime import datetime
import weakref

logger = logging.getLogger(__name__)


class MemoryLevel(Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MemoryStats:
    used_mb: float
    available_mb: float
    percent: float
    level: MemoryLevel
    timestamp: float


@dataclass
class MemoryThresholds:
    warning_percent: float = 75.0
    high_percent: float = 85.0
    critical_percent: float = 95.0
    gc_threshold: float = 80.0
    aggressive_gc_threshold: float = 90.0


class AllocationPool:
    """Pre-allocated memory pool for frequently created objects."""
    
    def __init__(self, factory, initial_size: int = 10, max_size: int = 50):
        self._factory = factory
        self._max_size = max_size
        self._pool: deque = deque(maxlen=max_size)
        self._in_use: int = 0
        self._lock = threading.Lock()
        
        for _ in range(initial_size):
            self._pool.append(factory())
    
    def acquire(self) -> Any:
        with self._lock:
            self._in_use += 1
            if self._pool:
                return self._pool.popleft()
            return self._factory()
    
    def release(self, obj: Any):
        with self._lock:
            self._in_use -= 1
            if len(self._pool) < self._max_size:
                self._pool.append(obj)
    
    @property
    def stats(self) -> Dict:
        return {
            "in_pool": len(self._pool),
            "in_use": self._in_use,
            "total": len(self._pool) + self._in_use
        }


class ModelCache:
    """LRU cache for ML models with memory management."""
    
    def __init__(self, max_memory_mb: float = 2000):
        self._max_memory_mb = max_memory_mb
        self._models: Dict[str, Any] = {}
        self._model_sizes: Dict[str, float] = {}
        self._last_used: Dict[str, float] = {}
        self._current_memory: float = 0.0
        self._lock = threading.Lock()
    
    def load(self, name: str, model: Any, size_mb: float) -> bool:
        with self._lock:
            if size_mb > self._max_memory_mb:
                logger.warning(f"Model {name} too large: {size_mb}MB > {self._max_memory_mb}MB")
                return False
            
            while self._current_memory + size_mb > self._max_memory_mb:
                if not self._evict_lru():
                    break
            
            if name in self._models:
                self._last_used[name] = datetime.now().timestamp()
                return True
            
            self._models[name] = model
            self._model_sizes[name] = size_mb
            self._current_memory += size_mb
            self._last_used[name] = datetime.now().timestamp()
            
            logger.info(f"Model loaded: {name} ({size_mb:.1f}MB)")
            return True
    
    def get(self, name: str) -> Optional[Any]:
        with self._lock:
            if name in self._models:
                self._last_used[name] = datetime.now().timestamp()
                return self._models[name]
            return None
    
    def unload(self, name: str):
        with self._lock:
            if name in self._models:
                del self._models[name]
                self._current_memory -= self._model_sizes.get(name, 0)
                del self._model_sizes[name]
                del self._last_used[name]
                logger.info(f"Model unloaded: {name}")
    
    def _evict_lru(self) -> bool:
        if not self._last_used:
            return False
        
        lru_name = min(self._last_used, key=self._last_used.get)
        self.unload(lru_name)
        return True
    
    @property
    def stats(self) -> Dict:
        return {
            "models_loaded": len(self._models),
            "memory_mb": self._current_memory,
            "max_memory_mb": self._max_memory_mb,
            "utilization": self._current_memory / self._max_memory_mb * 100 if self._max_memory_mb > 0 else 0
        }


class MemoryManager:
    """
    Central memory management system.
    Monitors usage, triggers GC, manages caches and model loading.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, thresholds: Optional[MemoryThresholds] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._thresholds = thresholds or MemoryThresholds()
        self._pools: Dict[str, AllocationPool] = {}
        self._model_cache = ModelCache()
        self._allocation_callbacks: List[Callable] = []
        self._gc_callbacks: List[Callable] = []
        
        self._gc_history: deque = deque(maxlen=50)
        self._memory_history: deque = deque(maxlen=300)
        
        self._gc_count = 0
        self._last_gc_time = 0.0
    
    @property
    def thresholds(self) -> MemoryThresholds:
        return self._thresholds
    
    def subscribe_allocation(self, callback: Callable):
        if callback not in self._allocation_callbacks:
            self._allocation_callbacks.append(callback)
    
    def subscribe_gc(self, callback: Callable):
        if callback not in self._gc_callbacks:
            self._gc_callbacks.append(callback)
    
    def register_pool(self, name: str, factory, initial_size: int = 10, max_size: int = 50):
        self._pools[name] = AllocationPool(factory, initial_size, max_size)
        logger.debug(f"Memory pool registered: {name}")
    
    def acquire_from_pool(self, pool_name: str) -> Optional[Any]:
        pool = self._pools.get(pool_name)
        if pool:
            return pool.acquire()
        return None
    
    def release_to_pool(self, pool_name: str, obj: Any):
        pool = self._pools.get(pool_name)
        if pool:
            pool.release(obj)
    
    def load_model(self, name: str, model: Any, size_mb: float) -> bool:
        return self._model_cache.load(name, model, size_mb)
    
    def get_model(self, name: str) -> Optional[Any]:
        return self._model_cache.get(name)
    
    def unload_model(self, name: str):
        self._model_cache.unload(name)
    
    def get_stats(self) -> MemoryStats:
        vm = psutil.virtual_memory()
        used_mb = vm.used / (1024 * 1024)
        available_mb = vm.available / (1024 * 1024)
        percent = vm.percent
        
        if percent >= self._thresholds.critical_percent:
            level = MemoryLevel.CRITICAL
        elif percent >= self._thresholds.high_percent:
            level = MemoryLevel.HIGH
        elif percent >= self._thresholds.warning_percent:
            level = MemoryLevel.ELEVATED
        else:
            level = MemoryLevel.NORMAL
        
        stats = MemoryStats(
            used_mb=used_mb,
            available_mb=available_mb,
            percent=percent,
            level=level,
            timestamp=datetime.now().timestamp()
        )
        
        self._memory_history.append(stats)
        return stats
    
    def check_and_garbage_collect(self) -> bool:
        stats = self.get_stats()
        did_gc = False
        
        if stats.percent >= self._thresholds.aggressive_gc_threshold:
            logger.warning(f"Aggressive GC triggered: {stats.percent:.1f}%")
            gc.collect(2)
            self._gc_count += 1
            did_gc = True
        elif stats.percent >= self._thresholds.gc_threshold:
            gc.collect(1)
            self._gc_count += 1
            did_gc = True
        
        if did_gc:
            self._last_gc_time = datetime.now().timestamp()
            self._gc_history.append({
                "timestamp": self._last_gc_time,
                "memory_percent": stats.percent,
                "aggressive": stats.percent >= self._thresholds.aggressive_gc_threshold
            })
            
            for callback in self._gc_callbacks:
                try:
                    callback(stats.percent)
                except Exception as e:
                    logger.error(f"GC callback error: {e}")
        
        return did_gc
    
    def force_gc(self, full: bool = True):
        generation = 2 if full else 0
        before = psutil.virtual_memory().percent
        gc.collect(generation)
        self._gc_count += 1
        after = psutil.virtual_memory().percent
        logger.info(f"Force GC: {before:.1f}% -> {after:.1f}%")
    
    def optimize(self) -> Dict:
        results = {
            "gc_runs": self._gc_count,
            "model_cache": self._model_cache.stats,
            "pools": {}
        }
        
        for name, pool in self._pools.items():
            results["pools"][name] = pool.stats
        
        if self.get_stats().percent >= self._thresholds.warning_percent:
            self.check_and_garbage_collect()
        
        return results
    
    def get_average_usage(self, seconds: int = 60) -> float:
        cutoff = datetime.now().timestamp() - seconds
        relevant = [s for s in self._memory_history if s.timestamp >= cutoff]
        
        if not relevant:
            return 0.0
        
        return sum(s.percent for s in relevant) / len(relevant)
    
    @property
    def model_cache(self) -> ModelCache:
        return self._model_cache
