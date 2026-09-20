import time
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("SATURDAY.Deadman")

class DeadmanSwitch:
    def __init__(self, config_path: str, crypto):
        self.config_path = Path(config_path)
        self.crypto = crypto
        self.last_heartbeat_file = self.config_path.parent / "heartbeat.enc"
        
        # Default config if not exists
        if not self.config_path.exists():
            self._save_config({
                "timeout_seconds": 86400 * 7, # 1 week
                "trigger_action": "release_instructions",
                "instructions": "Contact [+971 54 364 7837] for physical recovery of keys.",
                "enabled": True
            })

    def _save_config(self, config: dict):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        encrypted_data = self.crypto.encrypt_data(json.dumps(config).encode())
        tmp_path = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
        with open(tmp_path, 'wb') as f:
            f.write(encrypted_data)
        os.replace(tmp_path, self.config_path)

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        try:
            encrypted_data = self.config_path.read_bytes()
            decrypted_data = self.crypto.decrypt_data(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.warning(f"Deadman config unreadable (wrong passphrase or corrupt file): {e}")
            return {}

    def update_heartbeat(self):
        """Update the heartbeat timestamp securely."""
        heartbeat_data = {"last_seen": time.time()}
        encrypted_data = self.crypto.encrypt_data(json.dumps(heartbeat_data).encode())
        tmp_path = self.last_heartbeat_file.with_suffix(".tmp")
        with open(tmp_path, 'wb') as f:
            f.write(encrypted_data)
        os.replace(tmp_path, self.last_heartbeat_file)
        print("Heartbeat updated.")

    def check_status(self):
        """Check if the switch has been triggered."""
        config = self._load_config()
        if not config.get("enabled", False):
            return "Disabled"
        
        if not self.last_heartbeat_file.exists():
            return "Wait (No heartbeat yet)"
        
        try:
            encrypted_data = self.last_heartbeat_file.read_bytes()
            decrypted_data = self.crypto.decrypt_data(encrypted_data)
            heartbeat = json.loads(decrypted_data.decode())
            
            elapsed = time.time() - heartbeat.get("last_seen", 0)
            if elapsed > config.get("timeout_seconds", 86400):
                return "TRIGGERED"
            return f"Active (Last seen {elapsed:.1f}s ago)"
        except Exception as e:
            logger.warning(f"Deadman status check failed: {e}")
            return "Error checking status"

    def get_release_data(self):
        """If triggered, returns the release instructions."""
        status = self.check_status()
        if status == "TRIGGERED":
            config = self._load_config()
            return config.get("instructions", "No instructions found.")
        return "Not triggered."
