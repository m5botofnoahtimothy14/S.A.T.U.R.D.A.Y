import sys
import tempfile
import unittest
import os
import shutil
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from pmv.file_crypto import FileCrypto
from pmv.memory_engine import MemoryEngine
from pmv.deadman import DeadmanSwitch
from pmv.node_manager import NodeManager
from saturday.controller import MemoryController
from saturday.saturday_core import SATURDAYCore


def make_crypto(passphrase="test_passphrase_123"):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    salt_path = tmp.name
    os.unlink(salt_path)
    return FileCrypto(passphrase, salt_path=salt_path), salt_path


class TestSATURDAYSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_root = Path(tempfile.mkdtemp(prefix="saturday_test_"))
        cls.passphrase = "test_passphrase_123"
        cls._salt_files = []

    @classmethod
    def tearDownClass(cls):
        if cls.test_root.exists():
            shutil.rmtree(cls.test_root, ignore_errors=True)
        for f in cls._salt_files:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except Exception:
                pass

    def _tracked_crypto(self, passphrase=None):
        crypto, salt = make_crypto(passphrase or self.passphrase)
        type(self)._salt_files.append(salt)
        return crypto

    def test_encryption_decryption(self):
        crypto = self._tracked_crypto()
        original_data = b"Sensitive information for testing."
        encrypted = crypto.encrypt_data(original_data)
        decrypted = crypto.decrypt_data(encrypted)
        self.assertEqual(original_data, decrypted)
        print("DONE: Encryption/Decryption test passed.")

    def test_wrong_passphrase_cannot_decrypt(self):
        c1 = self._tracked_crypto()
        token = c1.encrypt_data(b"secret")
        # Same salt, wrong passphrase -> must fail, not silently succeed.
        c2 = FileCrypto("wrong_passphrase_999", salt_path=str(c1.salt_path))
        with self.assertRaises(Exception):
            c2.decrypt_data(token)
        print("DONE: Wrong-passphrase rejection test passed.")

    def test_short_passphrase_rejected(self):
        with self.assertRaises(ValueError):
            self._tracked_crypto("short")
        print("DONE: Short passphrase rejection test passed.")

    def test_memory_engine(self):
        crypto = self._tracked_crypto()
        engine = MemoryEngine(str(self.test_root / "vault"), crypto)

        content = "My secret project code is 42."
        tags = ["project", "secret"]
        entry_id = engine.store_entry(content, tags=tags)

        retrieved = engine.retrieve_entry(entry_id)
        self.assertEqual(retrieved['content'], content)
        self.assertIn("secret", retrieved['tags'])

        search_results = engine.search_by_tag("project")
        self.assertTrue(len(search_results) > 0)

        # Path traversal must not escape the vault.
        self.assertIsNone(engine.retrieve_entry("../settings"))
        self.assertFalse(engine.delete_entry("../settings"))

        # Delete works.
        self.assertTrue(engine.delete_entry(entry_id))
        self.assertIsNone(engine.retrieve_entry(entry_id))
        print("DONE: Memory Engine tests passed.")

    def test_memory_engine_rejects_empty(self):
        crypto = self._tracked_crypto()
        engine = MemoryEngine(str(self.test_root / "vault2"), crypto)
        with self.assertRaises(ValueError):
            engine.store_entry("   ")
        print("DONE: Empty-content rejection test passed.")

    def test_deadman_trigger(self):
        crypto = self._tracked_crypto()
        config_path = self.test_root / "deadman.json"
        dm = DeadmanSwitch(str(config_path), crypto)

        dm.update_heartbeat()
        status = dm.check_status()
        self.assertIn("Active", status)

        print("DONE: Deadman Switch heartbeat test passed.")

    def test_controller_lock(self):
        controller = MemoryController(self.passphrase, self.test_root)
        controller.mount_vaults()
        self.assertTrue(controller.vault_mounted)

        controller.secure_store("Something")
        controller.dismount_vaults()
        self.assertFalse(controller.vault_mounted)

        with self.assertRaises(Exception):
            controller.secure_store("Hidden")
        print("DONE: Controller lock/mount simulation passed.")

    def test_core_error_path_does_not_crash(self):
        """Regression: logger.exception(error=...) used to raise TypeError on any handler failure."""
        controller = MemoryController(self.passphrase, self.test_root)
        controller.mount_vaults()
        core = SATURDAYCore.__new__(SATURDAYCore)
        core.project_root = self.test_root
        core.pmv = controller
        core.is_running = True
        core._command_handlers = SATURDAYCore._build_command_handlers(core)
        # Force a handler failure (corrupt pmv) and verify graceful error string.
        core.pmv.memory_engine = None  # store will fail inside handler
        try:
            result = core.process_command("store hello world")
        finally:
            core.pmv.memory_engine = controller.memory_engine
            controller.dismount_vaults()
        self.assertTrue(result.startswith("❌ System Error:"))
        print("DONE: Core error-path regression test passed.")

    def test_core_store_retrieve_search_delete(self):
        project_root = self.test_root / "core_e2e"
        controller = MemoryController(self.passphrase, project_root)
        controller.mount_vaults()
        core = SATURDAYCore.__new__(SATURDAYCore)
        core.project_root = project_root
        core.pmv = controller
        core.is_running = True
        core._command_handlers = SATURDAYCore._build_command_handlers(core)
        try:
            out = core.process_command("store E2E secret payload tag:e2e,secret")
            self.assertIn("Stored securely", out)
            entry_id = out.rsplit(":", 1)[-1].strip()
            out = core.process_command(f"retrieve {entry_id}")
            self.assertIn("E2E secret payload", out)
            out = core.process_command("search tag:e2e")
            self.assertIn("Found", out)
            out = core.process_command(f"delete {entry_id}")
            self.assertIn("deleted", out.lower())
            out = core.process_command(f"retrieve {entry_id}")
            self.assertIn("not found", out.lower())
        finally:
            controller.dismount_vaults()
        print("DONE: Core E2E test passed.")

    def test_node_manager_corrupt_config(self):
        bad = self.test_root / "badnode.json"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("{not valid json")
        nm = NodeManager(str(bad))
        self.assertIn("node_id", nm.get_identity())
        with self.assertRaises(ValueError):
            nm.add_trusted_peer("bad peer!!$$$___###")
        print("DONE: Node corrupt-config test passed.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
