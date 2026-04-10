                      
import asyncio
import logging
import threading
import time
from typing import Callable, Coroutine, Any
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.TaskManager")

class BackgroundTask:
    def __init__(self, name: str, priority: int = 5):
        self.name = name
        self.priority = priority                                     
        self.created_at = time.time()
        self.status = "pending"                                              
        self.handle = None                                                 

class TaskManager:
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._registry: dict[str, BackgroundTask] = {}
        self._lock = threading.Lock()
        logger.info("Task Manager initialized.")

    def schedule(self, coro: Coroutine, name: str, priority: int = 5) -> asyncio.Task:
        
        task = BackgroundTask(name, priority)
        asyncio_task = asyncio.create_task(self._wrap_async(coro, task))
        task.handle = asyncio_task
        with self._lock:
            self._registry[name] = task
        logger.info(f"[+] Task scheduled: {name!r} (priority {priority})")
        return asyncio_task

    async def _wrap_async(self, coro: Coroutine, task: BackgroundTask):
        task.status = "running"
        try:
            await coro
            task.status = "done"
        except asyncio.CancelledError:
            task.status = "cancelled"
            logger.warning(f"Task cancelled: {task.name!r}")
        except Exception as e:
            task.status = "failed"
            logger.error(f"Task failed: {task.name!r} — {e}")
            self.event_bus.publish("task_failed", {"task": task.name, "error": str(e)})

    def schedule_thread(self, fn: Callable, name: str, priority: int = 5, *args, **kwargs):
        
        task = BackgroundTask(name, priority)
        t = threading.Thread(target=self._wrap_thread, args=(fn, task, args, kwargs), daemon=True)
        task.handle = t
        with self._lock:
            self._registry[name] = task
        t.start()
        logger.info(f"[+] Thread task started: {name!r} (priority {priority})")

    def _wrap_thread(self, fn: Callable, task: BackgroundTask, args, kwargs):
        task.status = "running"
        try:
            fn(*args, **kwargs)
            task.status = "done"
        except Exception as e:
            task.status = "failed"
            logger.error(f"Thread task failed: {task.name!r} — {e}")

    def cancel(self, name: str):
        
        with self._lock:
            task = self._registry.get(name)
        if task and isinstance(task.handle, asyncio.Task):
            task.handle.cancel()
            logger.info(f"Task {name!r} cancelled.")
        else:
            logger.warning(f"Task {name!r} not found or not cancellable.")

    def list_tasks(self) -> list[dict]:
        
        with self._lock:
            return [
                {
                    "name": t.name,
                    "status": t.status,
                    "priority": t.priority,
                    "age_sec": round(time.time() - t.created_at, 1)
                }
                for t in sorted(self._registry.values(), key=lambda x: x.priority)
            ]

    def clear_done(self):
        
        with self._lock:
            before = len(self._registry)
            self._registry = {k: v for k, v in self._registry.items()
                              if v.status not in ("done", "failed", "cancelled")}
            after = len(self._registry)
        logger.info(f"Registry purged: {before - after} tasks removed.")
