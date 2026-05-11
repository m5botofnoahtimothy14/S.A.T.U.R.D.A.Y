import os
import subprocess
import time
from pathlib import Path
from pmv.memory_engine import MemoryEngine
from pmv.file_crypto import FileCrypto
from pmv.deadman import DeadmanSwitch
from pmv.node_manager import NodeManager

class MemoryController:
    """The controlled interface between SATURDAY CORE and PMV."""
    
    def __init__(self, passphrase: str, project_root: Path):
        self.passphrase = passphrase
        self.project_root = project_root
        
        self.config_dir = project_root / "config"
        
        # Initialize Crypto (Keys are derived from passphrase + salt)
        self.crypto = FileCrypto(passphrase, salt_path=str(self.config_dir / "salt.dat"))
        
        # Sub-systems
        self.memory_engine = MemoryEngine(str(self.vault_dir / "memory"), self.crypto)
        self.deadman = DeadmanSwitch(str(self.config_dir / "deadman.json"), self.crypto)
        self.node_manager = NodeManager(str(self.config_dir / "node.json"))
        
        self.vault_mounted = False
        self.last_activity = time.time()

    def mount_vaults(self):
        """
        Simulates Mounting VeraCrypt containers.
        In production, this would call 'VeraCrypt.exe' with mount commands.
        """
        print("[PMV] Mounting encrypted containers...")
        # Simulation: In a real system, we'd check if the drive is mounted.
        # Here we just ensure the local directories exist and are 'ready'.
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.blackbox_dir.mkdir(parents=True, exist_ok=True)
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

    def secure_search(self, tag: str = None, start_time: float = None, end_time: float = None):
        self._check_lock()
        if tag:
            return self.memory_engine.search_by_tag(tag)
        if start_time and end_time:
            return self.memory_engine.search_by_time(start_time, end_time)
        return self.memory_engine.retrieve_all_entries()

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

    def auto_lock_check(self, timeout_seconds=300):
        """Automatically dismount if inactive."""
        if self.vault_mounted and (time.time() - self.last_activity > timeout_seconds):
            print("\n[SECURITY] Inactivity timeout reached. Auto-locking...")
            self.dismount_vaults()
            return True
        return False
