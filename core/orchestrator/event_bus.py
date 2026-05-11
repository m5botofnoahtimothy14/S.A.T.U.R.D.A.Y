"""
SATURDAY Enhanced Event Bus
Priority-based pub/sub with event filtering and async support
"""

import asyncio
import logging
import threading
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any, Optional, Set
from collections import defaultdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class EventPriority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    type: str
    data: Any = None
    priority: EventPriority = EventPriority.NORMAL
    source: Optional[str] = None
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    correlation_id: Optional[str] = None
    ttl: float = 60.0


class Subscription:
    def __init__(self, event_type: str, handler: Callable, priority: EventPriority = EventPriority.NORMAL,
                 filter_func: Optional[Callable] = None, subscriber_id: Optional[str] = None):
        self.event_type = event_type
        self.handler = handler
        self.priority = priority
        self.filter_func = filter_func
        self.subscriber_id = subscriber_id or id(handler)
        self.active = True
    
    def matches(self, event: Event) -> bool:
        if event.type != self.event_type:
            return False
        if self.filter_func:
            return self.filter_func(event)
        return True


class EventBus:
    """
    Enhanced Event Bus with priority-based routing and async support.
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Subscription]] = defaultdict(list)
        self._global_subscribers: List[Subscription] = []
        self._lock = threading.RLock()
        self._event_history: List[Event] = []
        self._max_history = 1000
        
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="EventBus")
        self._async_mode = True
        
        self._event_counts: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)
    
    def subscribe(self, event_type: str, handler: Callable, priority: EventPriority = EventPriority.NORMAL,
                  filter_func: Optional[Callable] = None, subscriber_id: Optional[str] = None):
        with self._lock:
            sub = Subscription(event_type, handler, priority, filter_func, subscriber_id)
            self._subscribers[event_type].append(sub)
            self._subscribers[event_type].sort(key=lambda s: s.priority, reverse=True)
            logger.debug(f"Subscribed: {event_type} -> {handler.__name__ if hasattr(handler, '__name__') else str(handler)}")
    
    def subscribe_all(self, handler: Callable, priority: EventPriority = EventPriority.NORMAL,
                      filter_func: Optional[Callable] = None):
        with self._lock:
            sub = Subscription("*", handler, priority, filter_func)
            self._global_subscribers.append(sub)
            self._global_subscribers.sort(key=lambda s: s.priority, reverse=True)
    
    def unsubscribe(self, event_type: str, handler_or_id: Any):
        with self._lock:
            if event_type in self._subscribers:
                if callable(handler_or_id):
                    self._subscribers[event_type] = [s for s in self._subscribers[event_type] if s.handler != handler_or_id]
                else:
                    self._subscribers[event_type] = [s for s in self._subscribers[event_type] if s.subscriber_id != handler_or_id]
    
    def unsubscribe_all(self, subscriber_id: str):
        with self._lock:
            for event_type in list(self._subscribers.keys()):
                self._subscribers[event_type] = [s for s in self._subscribers[event_type] if s.subscriber_id != subscriber_id]
            self._global_subscribers = [s for s in self._global_subscribers if s.subscriber_id != subscriber_id]
    
    def publish(self, event_type: str, data: Any = None, priority: EventPriority = EventPriority.NORMAL,
                source: Optional[str] = None, correlation_id: Optional[str] = None):
        event = Event(
            type=event_type,
            data=data,
            priority=priority,
            source=source,
            correlation_id=correlation_id
        )
        
        self._event_counts[event_type] += 1
        
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)
        
        if self._async_mode:
            asyncio.create_task(self._dispatch_event(event))
        else:
            self._dispatch_event_sync(event)
        
        return event
    
    async def publish_async(self, event_type: str, data: Any = None, priority: EventPriority = EventPriority.NORMAL,
                            source: Optional[str] = None):
        return self.publish(event_type, data, priority, source)
    
    async def _dispatch_event(self, event: Event):
        handlers_to_call = []
        
        with self._lock:
            for sub in self._subscribers.get(event.type, []):
                if sub.active and sub.matches(event):
                    handlers_to_call.append(sub)
            
            for sub in self._global_subscribers:
                if sub.active and sub.matches(event):
                    handlers_to_call.append(sub)
        
        for sub in handlers_to_call:
            try:
                if asyncio.iscoroutinefunction(sub.handler):
                    await sub.handler(event)
                else:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self._run_handler(sub.handler, event))
                    else:
                        loop.run_in_executor(self._executor, sub.handler, event)
            except Exception as e:
                self._error_counts[event.type] += 1
                logger.error(f"Event handler error ({event.type}): {e}")
    
    async def _run_handler(self, handler: Callable, event: Event):
        try:
            handler(event)
        except Exception as e:
            self._error_counts[event.type] += 1
            logger.error(f"Event handler error: {e}")
    
    def _dispatch_event_sync(self, event: Event):
        with self._lock:
            subscribers = list(self._subscribers.get(event.type, [])) + list(self._global_subscribers)
        
        for sub in subscribers:
            if sub.active and sub.matches(event):
                try:
                    result = sub.handler(event)
                    if asyncio.iscoroutine(result):
                        asyncio.create_task(result)
                except Exception as e:
                    self._error_counts[event.type] += 1
                    logger.error(f"Event handler error: {e}")
    
    def get_subscribers(self, event_type: str) -> List[str]:
        with self._lock:
            return [s.subscriber_id for s in self._subscribers.get(event_type, []) if s.active]
    
    def get_event_history(self, event_type: Optional[str] = None, count: int = 100) -> List[Event]:
        with self._lock:
            history = self._event_history
            if event_type:
                history = [e for e in history if e.type == event_type]
            return history[-count:]
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "event_types": len(self._subscribers),
                "total_subscribers": sum(len(subs) for subs in self._subscribers.values()),
                "global_subscribers": len(self._global_subscribers),
                "event_counts": dict(self._event_counts),
                "error_counts": dict(self._error_counts),
                "history_size": len(self._event_history)
            }
    
    def clear_history(self):
        with self._lock:
            self._event_history.clear()
    
    def reset_counts(self):
        with self._lock:
            self._event_counts.clear()
            self._error_counts.clear()
