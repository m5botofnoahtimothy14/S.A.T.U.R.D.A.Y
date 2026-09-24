"""Tests for identity, claps, mind, glow, heal, inbox — synthetic data only."""
import sys
import time
from pathlib import Path
from unittest import TestCase, main as test_main
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np


def stripes(vertical=True, seed=0):
    rng = np.random.default_rng(seed)
    base = np.zeros((200, 200), dtype=np.uint8)
    for i in range(0, 200, 10):
        if vertical:
            base[:, i:i + 5] = 200
        else:
            base[i:i + 5, :] = 200
    noise = rng.integers(0, 25, (200, 200)).astype(np.uint8)
    return np.clip(base.astype(int) + noise - 12, 0, 255).astype(np.uint8)


def tone(freq=440.0, secs=2.0, sr=16000, profile=(1.0, 0.5, 0.25)):
    """Vowel-like harmonic tone; profile = per-speaker formant shape."""
    t = np.arange(int(sr * secs)) / sr
    x = sum(a * np.sin(2 * np.pi * freq * (i + 1) * t) for i, a in enumerate(profile))
    x = x / max(1e-9, abs(x).max())
    return (9000 * x).astype(np.int16)


class TestFaceGallery(TestCase):
    def test_enroll_and_recognize(self):
        from saturday.identity import FaceGallery
        g = FaceGallery()
        self.assertTrue(g.available())
        n = g.train({"Noah": [stripes(True, s) for s in range(6)]})
        self.assertEqual(n, 6)
        name, dist = g.recognize(stripes(True, 99))
        self.assertEqual(name, "Noah")
        print(f"DONE: face recognize test passed ({name}@{dist}).")

    def test_stranger_rejected(self):
        from saturday.identity import FaceGallery
        g = FaceGallery()
        g.train({"Noah": [stripes(True, s) for s in range(6)]})
        name, dist = g.recognize(np.full((200, 200), 128, np.uint8))
        self.assertIsNone(name)
        self.assertGreater(dist, 55.0)
        print(f"DONE: stranger rejection test passed (dist {dist}).")


class TestVoicePrint(TestCase):
    def test_same_matches_different_not(self):
        from saturday.identity import mfcc_print, cosine_dist, VoiceVault
        me = dict(freq=130.0, profile=(1.0, 0.6, 0.4, 0.2))
        other = dict(freq=210.0, profile=(1.0, 0.2, 0.7, 0.1))
        a = mfcc_print(tone(**me))
        b = mfcc_print(tone(**me))
        c = mfcc_print(tone(**other))
        same, diff = cosine_dist(a, b), cosine_dist(a, c)
        self.assertLess(same, 0.05)
        self.assertLess(same, diff)
        vv = VoiceVault()
        en = vv.enroll([tone(**me), tone(**me), tone(**me)])
        self.assertTrue(en["success"])
        self.assertGreaterEqual(en["threshold"], 0.15)  # calibrated, not magic
        ok = vv.verify(tone(**me))
        self.assertTrue(ok["success"] and ok["match"] and ok["verdict"] == "owner")
        # dump/load roundtrip keeps the calibrated threshold
        vv2 = VoiceVault()
        self.assertTrue(vv2.load(vv.dump()))
        self.assertEqual(vv2.threshold, vv.threshold)
        print(f"DONE: voiceprint test passed (same={same}, diff={diff}, thr={en['threshold']}).")


class TestClaps(TestCase):
    def _click(self, n=1600, amp=9000.0):
        x = np.zeros(n, dtype=np.float64)
        x[n // 2:n // 2 + 40] = amp
        return x

    def test_single_clap(self):
        from saturday.claps import ClapListener
        fired = []
        ear = ClapListener(on_single=lambda: fired.append("s"), on_double=lambda: fired.append("d"))
        ear.feed(np.zeros(1600))
        ear.feed(self._click())
        time.sleep(1.1)
        ear.feed(np.zeros(1600))
        self.assertEqual(fired, ["s"])
        print("DONE: single clap test passed.")

    def test_double_clap(self):
        from saturday.claps import ClapListener
        fired = []
        ear = ClapListener(on_single=lambda: fired.append("s"), on_double=lambda: fired.append("d"))
        ear.feed(self._click())
        time.sleep(0.4)
        ear.feed(self._click())
        self.assertEqual(fired, ["d"])
        print("DONE: double clap test passed.")

    def test_silence_ignored(self):
        from saturday.claps import ClapListener
        fired = []
        ear = ClapListener(on_single=lambda: fired.append("s"), on_double=lambda: fired.append("d"))
        for _ in range(5):
            ear.feed(np.zeros(1600))
            time.sleep(0.3)
        self.assertEqual(fired, [])
        print("DONE: clap silence test passed.")


class TestGlow(TestCase):
    def test_math_and_states(self):
        from saturday.edgeglow import EdgeGlow, band_colors, STATES
        cols = band_colors((34, 211, 238), 10, 0.0)
        self.assertEqual(len(cols), 10)
        self.assertTrue(all(c.startswith("#") and len(c) == 7 for c in cols))
        for s in ("idle", "listening", "thinking", "speaking", "alert", "off"):
            self.assertIn(s, STATES)
        g = EdgeGlow()
        g.set_state("thinking")
        self.assertEqual(g.current(), "thinking")
        g.pulse("alert", seconds=0.2)
        self.assertEqual(g.current(), "alert")
        time.sleep(0.3)
        self.assertEqual(g.current(), "thinking")
        print("DONE: glow state test passed.")


class TestHeal(TestCase):
    def test_camera_restart_and_cooldown(self):
        from saturday.selfheal import SelfHeal
        core = MagicMock()
        core.pmv.vault_mounted = True
        session = MagicMock()
        cam = MagicMock()
        cam.running = False
        cam.last_error = "dead"
        session.camera = cam
        h = SelfHeal(core, session)
        with patch("saturday.brain.OllamaBrain") as OB:
            OB.return_value.available.return_value = True
            res = h.run_checks()
        by = {c["name"]: c for c in res}
        self.assertTrue(by["camera"]["healed"])
        cam.start.assert_called_once()
        res2 = h.run_checks()  # cooldown: no second restart storm
        self.assertEqual(cam.start.call_count, 1)
        self.assertIn(res2[0]["name"], ("camera",))
        print("DONE: selfheal restart test passed.")


class TestInbox(TestCase):
    def test_priority_order(self):
        from saturday.session import SessionManager
        core = MagicMock()
        mgr = SessionManager(core)
        mgr.inbox_add(goal="low", priority=1)
        mgr.inbox_add(goal="high", priority=9)
        mgr.inbox_add(goal="mid", priority=5)
        nxt = mgr._next_job()
        self.assertEqual(nxt["goal"], "high")
        print("DONE: inbox priority test passed.")

    def test_say_respects_dnd(self):
        from saturday.session import SessionManager
        core = MagicMock()
        mgr = SessionManager(core)
        mind = MagicMock()
        mind._can_speak.return_value = False
        mgr.mind = mind
        job = {"id": "T1", "kind": "say", "text": "hi", "status": "pending"}
        mgr._inbox_say(job)
        self.assertEqual(job["status"], "skipped")
        core._speak.assert_not_called()
        print("DONE: inbox DND test passed.")


class TestMind(TestCase):
    def _mind(self):
        from saturday.mind import MindLoop
        core = MagicMock()
        core.pmv.secure_search.return_value = []
        core._hydration_entries.return_value = []
        session = MagicMock()
        inbox_calls = []
        session.inbox_add.side_effect = lambda **kw: inbox_calls.append(kw) or "T1"
        core.session = session
        mind = MindLoop(core, observe_fn=lambda: {})
        mind.episode = MagicMock()
        mind.save_prefs = MagicMock()
        return mind, core, inbox_calls

    def test_water_selftask(self):
        mind, core, calls = self._mind()
        mind.tick({"present": "Noah", "commands": {"status": 2}})
        self.assertTrue(any(c.get("kind") == "say" and "water" in c.get("text", "") for c in calls))
        self.assertEqual(mind.prefs["top_commands"].get("status"), 2)
        self.assertEqual(mind.prefs["sightings"]["Noah"]["count"], 1)
        print("DONE: mind selftask test passed.")

    def test_spam_caps(self):
        mind, core, calls = self._mind()
        mind.prefs["speaks_this_hour"] = [time.time()] * 10
        self.assertFalse(mind._can_speak())
        mind.prefs["dnd"] = True
        self.assertFalse(mind._can_speak())
        print("DONE: mind caps test passed.")


if __name__ == "__main__":
    test_main(verbosity=2)
