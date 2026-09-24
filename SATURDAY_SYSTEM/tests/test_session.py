"""Tests for always-on session — fake camera, mocked backends."""
import sys
import time
from pathlib import Path
from unittest import TestCase, main as test_main
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from saturday.session import CameraService, SessionManager


class FakeCap:
    def __init__(self, *a, **k):
        self.n = 0

    def isOpened(self):
        return True

    def read(self):
        self.n += 1
        return True, np.zeros((480, 640, 3), dtype=np.uint8)

    def release(self):
        pass


class TestCameraService(TestCase):
    def test_persistent_hub(self):
        cam = CameraService(fps=20.0, ring_seconds=2.0)
        with patch("cv2.VideoCapture", FakeCap):
            cam.start()
            deadline = time.time() + 10
            while cam.get_frame() is None and time.time() < deadline:
                time.sleep(0.1)
            frame = cam.get_frame()
            self.assertIsNotNone(frame)
            self.assertEqual(frame.shape, (480, 640, 3))
            time.sleep(0.6)
            ring = cam.get_ring(1.0)
            self.assertGreater(len(ring), 3)
            st = cam.status()
            self.assertTrue(st["running"])
            self.assertTrue(st["opened_ok"])
            cam.stop()
            self.assertFalse(cam.running)
        print("DONE: camera hub test passed.")

    def test_no_camera_honest(self):
        cam = CameraService()
        with patch("cv2.VideoCapture", side_effect=RuntimeError("nope")):
            cam.start()
            time.sleep(0.3)
            self.assertFalse(cam.running or cam.opened_ok)
            self.assertIsNone(cam.get_frame())
        print("DONE: camera absent test passed.")


class TestSession(TestCase):
    def _core(self):
        core = MagicMock()
        core.pmv.vault_mounted = True
        core.agent_history = []
        core.screen = MagicMock()
        return core

    def test_boot_and_status(self):
        core = self._core()
        mgr = SessionManager(core)
        with patch("cv2.VideoCapture", FakeCap), \
             patch("saturday.session.SessionManager._preload_stt", lambda self: None), \
             patch("saturday.session.SessionManager._probe_brain", lambda self: None), \
             patch("saturday.session.SessionManager._start_homebot", lambda self: None), \
             patch("saturday.session.SessionManager._start_dashboard", lambda self: None):
            mgr.boot()
            time.sleep(0.5)
            st = mgr.status()
            self.assertIn("uptime_s", st)
            self.assertEqual(st["vault"], "mounted")
            mgr.shutdown()
        print("DONE: session boot test passed.")

    def test_queue_runs_background(self):
        core = self._core()
        core.pmv.secure_store.side_effect = lambda c, tags=None: "id-1"
        mgr = SessionManager(core)
        fake_brain = MagicMock()
        fake_brain.available.return_value = False
        with patch("saturday.brain.OllamaBrain", return_value=fake_brain):
            tid = mgr.queue_goal("research test")
            self.assertTrue(tid)
            deadline = time.time() + 15
            while not core.agent_history and time.time() < deadline:
                time.sleep(0.2)
            self.assertTrue(core.agent_history)
        print("DONE: task queue test passed.")


class TestSessionCommands(TestCase):
    def _core(self):
        from saturday.saturday_core import SATURDAYCore
        core = SATURDAYCore.__new__(SATURDAYCore)
        core.pmv = MagicMock()
        core.pmv.auto_lock_check.return_value = False
        core.screen = MagicMock()
        core.agent_history = []
        core._homebot = None
        core._dashboard = None
        core._brain_probe = None
        core.session = None
        core.is_running = True
        core._command_handlers = SATURDAYCore._build_command_handlers(core)
        return core

    def test_services_degraded(self):
        core = self._core()
        out = core.process_command("services", trusted=True)
        self.assertIn("degraded", out.lower())
        print("DONE: services degraded test passed.")

    def test_queue_needs_session(self):
        core = self._core()
        out = core.process_command("queue do things", trusted=True)
        self.assertIn("use `do`", out)
        print("DONE: queue fallback test passed.")

    def test_docker_guards(self):
        core = self._core()
        with patch("shutil.which", return_value=None):
            out = core.process_command("docker ps", trusted=True)
            self.assertIn("not installed", out)
        fake = MagicMock(returncode=0, stdout="abc123", stderr="")
        with patch("shutil.which", return_value="docker"), \
             patch("subprocess.run", return_value=fake):
            out = core.process_command("docker ps", trusted=True)
            self.assertIn("abc123", out)
        print("DONE: docker guard test passed.")

    def test_maps_route_mocked(self):
        core = self._core()
        geo = [{"display_name": "Dubai Mall, Dubai", "lat": "25.1", "lon": "55.2"}]
        route = {"routes": [{"distance": 15000, "duration": 1200}]}
        with patch.object(SATURDAYCore := type(core), "_osm_get",
                          side_effect=[geo, geo, geo, route]):
            out = core.process_command("maps Dubai Mall", trusted=True)
            self.assertIn("Dubai Mall", out)
            out = core.process_command("route A to B", trusted=True)
            self.assertIn("15.0 km", out)
        print("DONE: maps/route test passed.")

    def test_hr_ring_path(self):
        core = self._core()
        frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(100)]
        cam = MagicMock()
        cam.running = True
        cam.get_ring.return_value = [(time.time() - i * 0.1, f) for i, f in enumerate(frames)]
        session = MagicMock()
        session.camera = cam
        core.session = session
        with patch("saturday.senses.heart_rate",
                   return_value={"success": True, "bpm": 70.0, "confidence": 0.5,
                                 "seconds": 10.0, "note": "n/a"}) as mock_hr:
            out = core.process_command("hr 10", trusted=True)
            self.assertIn("70", out)
            mock_hr.assert_called_once()
            self.assertIn("frames", mock_hr.call_args[1])
        print("DONE: hr ring-path test passed.")


if __name__ == "__main__":
    test_main(verbosity=2)
