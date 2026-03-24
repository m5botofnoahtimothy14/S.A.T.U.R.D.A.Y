# core/event_bus.py
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
            # Capture the main event loop so we can dispatch from background threads.
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                self.loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop exists yet - will be set when needed
                pass
        self.lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.debug("Subscribed to event", event_type=event_type, handler=handler.__name__)

    def publish(self, event_type: str, data: Any = None):
        """
        Publish an event to all subscribers.
        - Works from both sync and async callers without needing 'await'.
        - Runs async handlers via create_task on the current loop.
        - Runs sync handlers immediately (or in the loop's executor if one exists).
        """
        logger.debug("Publishing event", event_type=event_type)

        handlers = self.subscribers.get(event_type, [])
        if not handlers:
            return

        # Ensure we have a loop
        if self.loop is None:
            try:
                self.loop = asyncio.get_event_loop()
            except RuntimeError:
                pass

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    # Run coroutine safely on the main loop even if called from another thread
                    if self.loop:
                        asyncio.run_coroutine_threadsafe(handler(data), self.loop)
                else:
                    if self.loop and self.loop.is_running():
                        # Schedule sync handler to keep thread-safe semantics
                        self.loop.call_soon_threadsafe(handler, data)
                    else:
                        handler(data)
            except Exception as e:
                logger.error("Handler dispatch failed", event_type=event_type, handler=getattr(handler, "__name__", str(handler)), error=str(e))
