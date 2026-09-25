"""Tests for SATURDAY Ears + voice orchestration — mocked, no hardware."""
import sys
import wave
from pathlib import Path
from unittest import TestCase, main as test_main
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from saturday import ears


def loud_samples(n=16000):
    t = np.arange(n) / 16000.0
    return (3000 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)


class TestEars(TestCase):
    def test_heard_gate(self):
        self.assertFalse(ears.heard(np.zeros(16000, dtype=np.int16)))
        self.assertTrue(ears.heard(loud_samples()))
        print("DONE: energy gate test passed.")

    def test_save_wav_roundtrip(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="saturday_wav_"))
        try:
            p = ears.save_wav(loud_samples(8000), 16000, str(tmp / "t.wav"))
            with wave.open(p, "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1)
                self.assertEqual(wf.getsampwidth(), 2)
                self.assertEqual(wf.getframerate(), 16000)
                self.assertEqual(wf.getnframes(), 8000)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        print("DONE: wav roundtrip test passed.")

    def test_hear_once_silence_never_transcribes(self):
        quiet = {"success": True, "samples": np.zeros(16000, dtype=np.int16),
                 "samplerate": 16000, "rms": 0.0}
        with patch.object(ears, "capture", return_value=quiet), \
             patch.object(ears, "transcribe", side_effect=AssertionError("must not transcribe silence")):
            res = ears.hear_once(1.0)
            self.assertTrue(res["success"])
            self.assertFalse(res["heard_something"])
        print("DONE: silence honesty test passed.")

    def test_hear_once_success(self):
        cap = {"success": True, "samples": loud_samples(), "samplerate": 16000, "rms": 2121.0}
        with patch.object(ears, "capture", return_value=cap), \
             patch.object(ears, "transcribe",
                          return_value={"success": True, "text": "hello saturday",
                                        "language": "en", "heard_something": True}):
            res = ears.hear_once(1.0)
            self.assertEqual(res["text"], "hello saturday")
        print("DONE: hear-once test passed.")

    def test_listen_orchestrates_hear_command_speak(self):
        from saturday.saturday_core import SATURDAYCore
        core = SATURDAYCore.__new__(SATURDAYCore)
        core.pmv = MagicMock()
        core.pmv.auto_lock_check.return_value = False
        core.screen = MagicMock()
        core.agent_history = []
        core._current_trusted = True
        core.is_running = True
        core._command_handlers = SATURDAYCore._build_command_handlers(core)

        def cap(seconds=5.0, samplerate=16000):
            return {"success": True, "samples": loud_samples(1600),
                    "samplerate": samplerate, "rms": 2121.0}

        heard_texts = iter(["status", "goodbye"])
        tr = {"success": True, "language": "en", "heard_something": True}
        with patch.object(ears, "capture", side_effect=cap), \
             patch.object(ears, "heard", return_value=True), \
             patch.object(ears, "transcribe",
                          side_effect=lambda **kw: {**tr, "text": next(heard_texts)}), \
             patch.object(SATURDAYCore, "_speak") as mock_speak:
            out = core.process_command("listen 1", trusted=True)
            self.assertIn("Goodbye", out)
            mock_speak.assert_called()  # result was spoken, not just printed
        print("DONE: listen orchestration test passed.")

    def test_say_speaks(self):
        from saturday.saturday_core import SATURDAYCore
        core = SATURDAYCore.__new__(SATURDAYCore)
        core.pmv = MagicMock()
        core.pmv.auto_lock_check.return_value = False
        core._current_trusted = True
        core._command_handlers = SATURDAYCore._build_command_handlers(core)
        with patch("interface.voice.SATURDAYVoice") as MockVoice:
            out = core.process_command("say Systems online", trusted=True)
            self.assertIn("Said", out)
            MockVoice.return_value.speak.assert_called_once()
            self.assertIn("Systems online", MockVoice.return_value.speak.call_args[0][0])
        print("DONE: say test passed.")

    def test_windows_voice_knobs(self):
        from interface.voice import SATURDAYVoice
        v = SATURDAYVoice(core=None)
        with patch.dict("os.environ", {"SATURDAY_TTS_VOLUME": "42", "SATURDAY_TTS_RATE": "2"}), \
             patch("subprocess.run") as mock_run:
            self.assertTrue(v._windows_speak("hi"))
            script = mock_run.call_args[0][0][-1]
            self.assertIn("$s.Volume=42", script)
            self.assertIn("$s.Rate=2", script)
        with patch.dict("os.environ", {"SATURDAY_TTS_VOLUME": "9999", "SATURDAY_TTS_RATE": "-99"}), \
             patch("subprocess.run") as mock_run:
            v._windows_speak("hi")
            script = mock_run.call_args[0][0][-1]
            self.assertIn("$s.Volume=100", script)
            self.assertIn("$s.Rate=-10", script)
        print("DONE: voice knob test passed.")


if __name__ == "__main__":
    test_main(verbosity=2)
