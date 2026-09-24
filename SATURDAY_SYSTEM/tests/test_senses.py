"""Tests for SATURDAY Senses — synthetic signals, no camera needed."""
import sys
import time
from pathlib import Path
from unittest import TestCase, main as test_main

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from saturday import senses


class TestSenses(TestCase):
    def test_rppg_detects_synthetic_72bpm(self):
        """The money test: 1.2 Hz green pulsatility must read ~72 BPM."""
        fps, secs, freq = 30.0, 20.0, 1.2
        t = np.arange(int(fps * secs)) / fps
        rng = np.random.default_rng(7)
        values = (128.0 + 4.0 * np.sin(2 * np.pi * freq * t) + rng.normal(0, 0.5, len(t))).tolist()
        res = senses.bpm_from_green_series(values, fps)
        self.assertTrue(res["success"], res)
        self.assertGreaterEqual(res["bpm"], 65.0)
        self.assertLessEqual(res["bpm"], 79.0)
        self.assertGreater(res["confidence"], 0.05)
        print(f"DONE: synthetic rPPG test passed ({res['bpm']} BPM).")

    def test_rppg_rejects_flat_and_short(self):
        flat = [128.0] * 600
        res = senses.bpm_from_green_series(flat, 30.0)
        self.assertFalse(res["success"])
        short = [128.0 + np.sin(i) for i in range(30)]
        res = senses.bpm_from_green_series(short, 30.0)
        self.assertFalse(res["success"])
        print("DONE: rPPG rejection test passed.")

    def test_people_and_faces_on_blank(self):
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        p = senses.find_people(blank)
        self.assertTrue(p["success"])
        self.assertEqual(p["count"], 0)
        f = senses.find_faces(blank)
        self.assertTrue(f["success"])
        self.assertEqual(f["count"], 0)
        print("DONE: detectors blank-image test passed.")

    def test_mood_without_model_is_honest(self):
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        res = senses.mood(blank, model_path="definitely/not/here.onnx")
        self.assertFalse(res["success"])
        self.assertIn("not found", res["error"])
        print("DONE: mood fallback test passed.")

    def test_mood_model_file_loads(self):
        path = senses.emotion_model_path(str(PROJECT_ROOT))
        if not path.exists():
            self.skipTest("expression model not downloaded")
        import onnxruntime as ort
        s = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        self.assertEqual(s.get_inputs()[0].shape, [1, 1, 64, 64])
        print("DONE: mood model load test passed.")

    def test_wellness_composite(self):
        calm = senses.wellness(hr_bpm=68, mood_label="happy", sad_score=0.0)
        self.assertTrue(calm["success"])
        self.assertEqual(calm["anxiety_level"], "calm")
        self.assertIsNone(calm["danger"])
        bad = senses.wellness(hr_bpm=110, mood_label="anxious", sad_score=0.7)
        self.assertIn(bad["anxiety_level"], ("elevated", "high"))
        self.assertGreater(bad["sadness"], 50)
        self.assertIn("disclaimer", bad)
        print("DONE: wellness composite test passed.")

    def test_hydration_math(self):
        now = time.time()
        entries = []
        self.assertTrue(senses.log_drink(entries, 500, now)["success"])
        self.assertTrue(senses.log_drink(entries, 750, now)["success"])
        self.assertFalse(senses.log_drink(entries, 5000, now)["success"])
        st = senses.water_status(entries, goal_ml=3000.0, now=now)
        self.assertEqual(st["today_ml"], 1250.0)
        old = [{"ml": 9999, "at": now - 90000}]
        self.assertEqual(senses.today_total(old, now), 0.0)
        print("DONE: hydration test passed.")


if __name__ == "__main__":
    test_main(verbosity=2)
