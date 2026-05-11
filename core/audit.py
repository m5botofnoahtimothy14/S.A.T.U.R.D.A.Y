               

import logging
from core.state import SystemState
import threading
import time
import json
logger = logging.getLogger("SATURDAY.Audit")
logger.setLevel(logging.INFO)
class AuditLogger:
    def __init__(self, state: SystemState):
        self.state = state
        self.audit_file = "logs/audit.json"
        self.lock = threading.Lock()
        self.load_audit()
    def load_audit(self):
        try:
            with open(self.audit_file, "r") as f:
                self.audit_log = json.load(f)
        except FileNotFoundError:
            self.audit_log = []
    def log(self, user, action, module=None, details=None):
        with self.lock:
            entry = {
                "timestamp": time.time(),
                "user": user,
                "action": action,
                "module": module,
                "details": details
            }
            self.audit_log.append(entry)
            with open(self.audit_file, "w") as f:
                json.dump(self.audit_log, f, indent=4)
            logger.info(f"Audit logged: {entry}")
