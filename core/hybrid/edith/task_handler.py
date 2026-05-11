                              
import logging
from core.event_bus import EventBus

logger = logging.getLogger("SATURDAY.EDITH.Tasks")

class EdithTaskHandler:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        logger.info("EDITH Task Handler initialized.")

    def execute_task(self, task_name: str, params: dict = None):
        logger.info(f"EDITH executing task: {task_name}")
                                   
