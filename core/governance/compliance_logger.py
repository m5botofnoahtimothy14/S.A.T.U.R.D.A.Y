                                 
import json
import time

class ComplianceLogger:
    def __init__(self):
        self.log_file = "logs/compliance.json"

    def log_event(self, event_type, details):
        entry = {
            "timestamp": time.time(),
            "type": event_type,
            "details": details
        }
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except:
            pass
