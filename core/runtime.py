# core/runtime.py
import time
import os
import psutil
import logging

logger = logging.getLogger("AEGIS.Runtime")

class RuntimeStats:
    def __init__(self):
        self.start_time = time.time()
        self.pid = os.getpid()

    def get_uptime(self):
        return time.time() - self.start_time

    def get_resource_usage(self):
        process = psutil.Process(self.pid)
        return {
            "memory_mb": process.memory_info().rss / (1024 * 1024),
            "cpu_percent": process.cpu_percent(interval=0.1),
            "uptime_sec": self.get_uptime()
        }

    def log_status(self):
        stats = self.get_resource_usage()
        logger.info(f"Runtime Status: {stats}")
        return stats
