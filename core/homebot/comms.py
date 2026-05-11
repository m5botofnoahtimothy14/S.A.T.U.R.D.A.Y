                  
import threading
import logging
import queue

logger = logging.getLogger("SATURDAY.HomeBot.Comms")

class Comms:
    
    def __init__(self):
        self.command_queue = queue.Queue()
        self.telemetry_queue = queue.Queue()
        self.listening = True
        threading.Thread(target=self._process_commands, daemon=True).start()

    def send_command(self, cmd):
        
        logger.info(f"Received command: {cmd}")
        self.command_queue.put(cmd)

    def send_telemetry(self, data):
        
        logger.info(f"Telemetry sent: {data}")
        self.telemetry_queue.put(data)

    def _process_commands(self):
        while self.listening:
            if not self.command_queue.empty():
                cmd = self.command_queue.get()
                logger.info(f"Processing command: {cmd}")
                                                
