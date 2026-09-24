"""Tests for SATURDAY Brain — Ollama HTTP mocked, no server needed."""
import sys
from pathlib import Path
from unittest import TestCase, main as test_main
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from saturday.brain import OllamaBrain
from saturday.agent import AgentTask


def brain():
    b = OllamaBrain(model="llama3.2-test", timeout=5)
    b._available = None
    return b


class TestBrain(TestCase):
    def test_available_true_when_model_pulled(self):
        b = brain()
        with patch.object(OllamaBrain, "_get", return_value={"models": [{"name": "llama3.2-test:latest"}]}):
            self.assertTrue(b.available())
        print("DONE: brain available test passed.")

    def test_available_false_when_server_down(self):
        b = brain()
        with patch.object(OllamaBrain, "_get", side_effect=RuntimeError("nope")):
            self.assertFalse(b.available())
        print("DONE: brain offline test passed.")

    def test_decide_parses_action(self):
        b = brain()
        import time
        b._available = True
        b._checked_at = time.time()  # within cooldown: no re-probe
        task = AgentTask("open gmail", [])
        fake = '{"action": "open_url", "args": {"url": "https://mail.google.com"}, "why": "start here"}'
        with patch.object(OllamaBrain, "_generate", return_value=fake):
            step = b.decide(task, {"success": True})
            self.assertEqual(step["action"], "open_url")
            self.assertEqual(step["args"]["url"], "https://mail.google.com")
        print("DONE: brain decide test passed.")

    def test_decide_falls_back_to_ask(self):
        b = brain()
        b._available = True
        task = AgentTask("goal", [])
        with patch.object(OllamaBrain, "_generate", return_value="not json at all !!!"):
            step = b.decide(task, {})
            self.assertEqual(step["action"], "ask")
        b._available = False
        step = b.decide(task, {})
        self.assertEqual(step["action"], "ask")
        print("DONE: brain fallback test passed.")

    def test_ground_parses_box(self):
        b = brain()
        import tempfile
        from PIL import Image
        tmp = Path(tempfile.mkdtemp(prefix="saturday_ground_"))
        try:
            img = tmp / "shot.png"
            Image.new("RGB", (64, 64), (0, 0, 0)).save(img)
            with patch.object(OllamaBrain, "_generate", return_value="100 200 300 400"):
                pt = b.ground("Compose button", str(img), image_size=(1920, 1080))
                self.assertEqual(pt, {"x": int(0.2 * 1920), "y": int(0.3 * 1080)})
            with patch.object(OllamaBrain, "_generate", return_value="no idea"):
                self.assertIsNone(b.ground("x", str(img)))
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        print("DONE: brain grounding test passed.")

    def test_core_brain_refuses_remote(self):
        from saturday.saturday_core import SATURDAYCore
        core = SATURDAYCore.__new__(SATURDAYCore)
        core.pmv = MagicMock()
        core.pmv.auto_lock_check.return_value = False
        core.screen = MagicMock()
        core.agent_history = []
        core._current_trusted = False
        core.is_running = True
        core._command_handlers = SATURDAYCore._build_command_handlers(core)
        out = core.process_command("brain take over the pc", trusted=False)
        self.assertIn("local-only", out)
        print("DONE: brain remote refusal test passed.")

    def test_core_brain_reports_offline(self):
        from saturday.saturday_core import SATURDAYCore
        core = SATURDAYCore.__new__(SATURDAYCore)
        core.pmv = MagicMock()
        core.pmv.auto_lock_check.return_value = False
        core.screen = MagicMock()
        core.agent_history = []
        core._current_trusted = True
        core.is_running = True
        core._command_handlers = SATURDAYCore._build_command_handlers(core)
        with patch("saturday.brain.OllamaBrain") as MockBrain:
            MockBrain.return_value.available.return_value = False
            out = core.process_command("brain do stuff", trusted=True)
            self.assertIn("offline", out.lower())
        print("DONE: brain offline message test passed.")


if __name__ == "__main__":
    test_main(verbosity=2)
