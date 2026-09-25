"""Tests for presence + human voice — mocked camera, no hardware."""
import sys
import time
from pathlib import Path
from unittest import TestCase, main as test_main
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from saturday import humanvoice as hv


class TestHumanLines(TestCase):
    def test_lines_are_sentences(self):
        self.assertIn("SATURDAY", hv.startup_line(True, True) or "SATURDAY")
        line = hv.arrival_line("Noah", "happy")
        self.assertIn("Noah", line)
        self.assertFalse(any(e in line for e in "❌✅📷"))
        hv.hydration_line("Noah", 5.0)
        b = hv.briefing_speech("Noah", 100, 3000, 3, ["status", "sense"], "live")
        self.assertIn("Noah", b)
        print("DONE: human lines test passed.")

    def test_naturalize_strips_machine(self):
        s = hv.naturalize("💓 Heart rate: 72 BPM (confidence 86%, 10s scan)\n   estimates only")
        self.assertNotIn("💓", s)
        self.assertNotIn("BPM", s)
        s2 = hv.naturalize("❌ Vault is locked. Mount required.")
        self.assertNotIn("❌", s2)
        s3 = hv.naturalize("")
        self.assertTrue(s3)
        s4 = hv.naturalize("12345 67890")
        self.assertTrue(s4)
        print("DONE: naturalize test passed.")


class TestVoiceGate(TestCase):
    def test_permissive_without_enrollment(self):
        core = MagicMock()
        core._voicevault.return_value.print = None
        g = hv.VoiceGate(core)
        r = g.who_authorized(np.zeros(16000, dtype=np.int16))
        self.assertTrue(r["authorized"])
        print("DONE: gate permissive test passed.")

    def test_gates_when_enrolled(self):
        core = MagicMock()
        vv = MagicMock()
        vv.print = "exists"
        vv.verify.return_value = {"success": True, "match": False,
                                  "verdict": "guest/unknown", "distance": 0.5}
        core._voicevault.return_value = vv
        g = hv.VoiceGate(core)
        r = g.who_authorized(np.zeros(16000, dtype=np.int16))
        self.assertFalse(r["authorized"])
        self.assertEqual(r["verdict"], "guest/unknown")
        print("DONE: gate enrolled test passed.")


class TestPresence(TestCase):
    def _session(self):
        from saturday.session import SessionManager
        core = MagicMock()
        core.is_running = True
        core.pmv.vault_mounted = True
        core._gallery.return_value.recognize.return_value = ("Noah", 20.0)
        mgr = SessionManager(core)
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        mgr.camera = MagicMock()
        mgr.camera.running = True
        mgr.camera.get_frame.return_value = frame
        return mgr, core, frame

    def test_greets_once_per_arrival(self):
        mgr, core, frame = self._session()
        from saturday.presence import PresenceLoop
        with patch("saturday.senses.find_faces",
                   return_value={"success": True, "count": 1,
                                 "boxes": [{"x": 10, "y": 10, "w": 80, "h": 80}]}), \
             patch("saturday.senses.mood", return_value={"success": True, "mood": "happy"}):
            p = PresenceLoop(mgr)
            first = p.tick()
            self.assertIsNotNone(first)
            self.assertIn("Noah", first)
            second = p.tick()  # same arrival -> silence
            self.assertIsNone(second)
            core._speak.assert_called_once()
        print("DONE: presence greet-once test passed.")

    def test_no_face_no_greet(self):
        mgr, core, frame = self._session()
        from saturday.presence import PresenceLoop
        with patch("saturday.senses.find_faces",
                   return_value={"success": True, "count": 0, "boxes": []}):
            p = PresenceLoop(mgr)
            self.assertIsNone(p.tick())
            core._speak.assert_not_called()
        print("DONE: presence no-face test passed.")

    def test_dnd_suppresses(self):
        mgr, core, frame = self._session()
        mind = MagicMock()
        mind.prefs = {"dnd": True}
        mgr.mind = mind
        from saturday.presence import PresenceLoop
        with patch("saturday.senses.find_faces",
                   return_value={"success": True, "count": 1,
                                 "boxes": [{"x": 0, "y": 0, "w": 60, "h": 60}]}):
            p = PresenceLoop(mgr)
            self.assertIsNone(p.tick())
            core._speak.assert_not_called()
        print("DONE: presence dnd test passed.")


if __name__ == "__main__":
    test_main(verbosity=2)
