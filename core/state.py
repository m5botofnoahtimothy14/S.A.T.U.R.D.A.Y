               
import threading
import time
import json
from core.config import ConfigManager

class SystemState:
    def __init__(self):
        self.lock = threading.Lock()
        self.state_file = "core/state.json"
        self.config = ConfigManager()
                                          
        self.state = {
            "user_mode": "Sir",                 
            "aeigis_active": True,
            "edith_active": True,
            "homebot_connected": False,
            "cloud_session": False,
            "last_command": None,
            "security_alerts": [],
            "active_modules": []
        }
        self.load_state()

    def load_state(self):
        try:
            with open(self.state_file, "r") as f:
                self.state.update(json.load(f))
        except FileNotFoundError:
            self.save_state()

    def save_state(self):
        with self.lock:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=4)

    def update_state(self, key, value):
        with self.lock:
            self.state[key] = value
            self.save_state()

    def get_state(self, key, default=None):
        return self.state.get(key, default)

    def append_to_list(self, key, value):
        with self.lock:
            if key not in self.state:
                self.state[key] = []
            self.state[key].append(value)
            self.save_state()

def autosave_state(system_state: SystemState, interval=10):
    def _autosave():
        while True:
            time.sleep(interval)
            system_state.save_state()
    threading.Thread(target=_autosave, daemon=True).start()
