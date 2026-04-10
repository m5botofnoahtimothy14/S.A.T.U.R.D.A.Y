                            
import logging
import threading
import time
import schedule

logger = logging.getLogger("AEGIS.Services.Scheduler")

class TaskScheduler:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._run_loop, daemon=True).start()
        logger.info("Task Scheduler started.")

    def _run_loop(self):
                          
        schedule.every(1).hours.do(lambda: self.event_bus.publish("maintenance_task", "health_check"))
        
        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def add_task(self, interval_mins, task_func):
        schedule.every(interval_mins).minutes.do(task_func)
        logger.info(f"Task scheduled every {interval_mins} minutes.")
