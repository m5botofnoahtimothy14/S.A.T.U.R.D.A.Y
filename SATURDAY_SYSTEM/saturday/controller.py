import os
import subprocess
import time
import json
import logging
from pathlib import Path
from pmv.memory_engine import MemoryEngine
from pmv.file_crypto import FileCrypto
from pmv.deadman import DeadmanSwitch
from pmv.node_manager import NodeManager

logger = logging.getLogger("SATURDAY.Controller")

class MemoryController:
    """The controlled interface between SATURDAY CORE and PMV."""
    
    def __init__(self, passphrase: str, project_root: Path):
        self.passphrase = passphrase
        self.project_root = project_root
        self.config_dir = project_root / "config"
        self.settings = self._load_settings()

        paths = self.settings.get("paths", {})
        self.vault_dir = self._resolve_dir(paths.get("vault"), "./vault")
        self.blackbox_dir = self._resolve_dir(paths.get("blackbox"), "./blackbox")
        self.sync_staging = self._resolve_dir(paths.get("sync_staging"), "./staging")

        self.auto_lock_timeout = self.settings.get("security", {}).get("auto_lock_timeout", 300)
        self.kdf_iterations = self.settings.get("security", {}).get("kdf_iterations", 100000)

        self.crypto = FileCrypto(passphrase, salt_path=str(self.config_dir / "salt.dat"), iterations=self.kdf_iterations)
        
        self.memory_engine = MemoryEngine(str(self.vault_dir / "memory"), self.crypto)
        self.deadman = DeadmanSwitch(str(self.config_dir / "deadman.json"), self.crypto)
        self.node_manager = NodeManager(str(self.config_dir / "node.json"))
        
        self.vault_mounted = False
        self.last_activity = time.time()

    def _load_settings(self):
        settings_path = self.project_root / "config" / "settings.json"
        if settings_path.exists():
            try:
                with open(settings_path, 'r') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
                logger.warning("settings.json is not an object; using defaults.")
            except Exception as e:
                logger.warning(f"Could not parse settings.json ({e}); using defaults.")
        return {}

    def _resolve_dir(self, configured: str, default: str) -> Path:
        raw = configured or default
        p = Path(raw)
        if not p.is_absolute():
            p = self.project_root / p
        return p.resolve()

    def mount_vaults(self):
        """Simulate vault mounting and prepare encrypted containers."""
        print("[PMV] Mounting encrypted containers...")
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.blackbox_dir.mkdir(parents=True, exist_ok=True)
        self.sync_staging.mkdir(parents=True, exist_ok=True)
        self.vault_mounted = True
        print("[PMV] Vaults mounted (Session Active).")

    def dismount_vaults(self):
        """Simulates Dismounting."""
        print("[PMV] Securing and dismounting containers...")
        self.vault_mounted = False
        # In PRD: subprocess.run(["veracrypt", "/dismount", "/force", "/silent"])
        print("[PMV] Vaults dismounted.")

    def secure_store(self, content: str, entry_type: str = "general", tags: list = None):
        self._check_lock()
        return self.memory_engine.store_entry(content, entry_type, tags)

    def secure_retrieve(self, entry_id: str):
        self._check_lock()
        return self.memory_engine.retrieve_entry(entry_id)

    def secure_search(self, tag: str = None, start_time: float = None, end_time: float = None, limit: int = 50):
        self._check_lock()
        if tag:
            results = self.memory_engine.search_by_tag(tag)
        elif start_time and end_time:
            results = self.memory_engine.search_by_time(start_time, end_time)
        else:
            results = self.memory_engine.retrieve_all_entries(limit=limit * 4)
        return results[:limit]

    def secure_delete(self, entry_id: str) -> bool:
        self._check_lock()
        return self.memory_engine.delete_entry(entry_id)

    def is_locked(self) -> bool:
        return not self.vault_mounted

    def update_heartbeat(self):
        self.deadman.update_heartbeat()

    def get_deadman_status(self):
        return self.deadman.check_status()

    def node_status(self):
        return self.node_manager.status()

    def _check_lock(self):
        if not self.vault_mounted:
            raise Exception("Vault is locked. Mount required.")
        self.last_activity = time.time()

    def clear_credentials(self):
        self.passphrase = None
        self.crypto.clear()

    def auto_lock_check(self, timeout_seconds: int = None):
        if timeout_seconds is None:
            timeout_seconds = self.auto_lock_timeout
        if self.vault_mounted and (time.time() - self.last_activity > timeout_seconds):
            print("\n[SECURITY] Inactivity timeout reached. Auto-locking...")
            self.dismount_vaults()
            return True
        return False
