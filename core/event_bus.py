                   

import asyncio
import inspect
import threading
import structlog
from typing import Callable, Dict, List, Any
logger = structlog.get_logger("AEGIS.EventBus")
class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.loop = None
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                self.loop = asyncio.get_event_loop()
            except RuntimeError:
                pass
        self.lock = threading.Lock()
    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.debug("Subscribed to event", event_type=event_type, handler=handler.__name__)
    def publish(self, event_type: str, data: Any = None):
        logger.debug("Publishing event", event_type=event_type)
        handlers = self.subscribers.get(event_type, [])
        if not handlers:
            return
        if self.loop is None:
            try:
                self.loop = asyncio.get_event_loop()
            except RuntimeError:
                pass
        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    if self.loop:
                        asyncio.run_coroutine_threadsafe(handler(data), self.loop)
                else:
                    if self.loop and self.loop.is_running():
                        self.loop.call_soon_threadsafe(handler, data)
                    else:
                        handler(data)
            except Exception as e:
                logger.error("Handler dispatch failed", event_type=event_type, handler=getattr(handler, "__name__", str(handler)), error=str(e))
