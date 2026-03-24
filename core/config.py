# core/config.py
import json
import os

CONFIG_FILE = "core/config.json"

class ConfigManager:
    def __init__(self):
        self.config = {}
        if not os.path.exists(CONFIG_FILE):
            self.create_default_config()
        self.load_config()

    def create_default_config(self):
        default_config = {
            "wake_word": "aegis",
            "edith_wake_word": "edith",
            "voices": {
                "aegis": {"gender": "male", "rate": 160, "volume": 1.0},
                "edith": {"gender": "female", "rate": 170, "volume": 1.0}
            },
            "cloud": {
                "endpoint": "https://aegis-cloud.example.com",
                "sync_interval": 30
            },
            "homebot": {
                "device_ip": "192.168.0.100",
                "motor_max_speed": 100
            },
            "security": {
                "cpu_threshold": 85,
                "mem_threshold": 90
            },
            "christianity_core": {
                "scripture_db_path": "christianity_core/scripture_db.json"
            },
            "logging": {
                "event_log": "logs/events.log",
                "security_log": "logs/security.log"
            }
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=4)

    def load_config(self):
        with open(CONFIG_FILE, "r") as f:
            self.config = json.load(f)

    def get(self, key_path, default=None):
        """
        Access nested config values using dot notation.
        Example: get("voices.aegis.rate")
        """
        keys = key_path.split(".")
        val = self.config
        try:
            for k in keys:
                val = val[k]
            return val
        except KeyError:
            return default

    def set(self, key_path, value):
        keys = key_path.split(".")
        cfg = self.config
        for k in keys[:-1]:
            cfg = cfg.setdefault(k, {})
        cfg[keys[-1]] = value
        self.save()

    def save(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)
