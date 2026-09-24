"""SATURDAY Claps — acoustic remote control. Single clap = attention, double = idle.

How it hears: mic stream → per-block peak vs slow noise floor. A clap is a
sharp transient (fast attack, loud vs floor). Two transients 180–900ms
apart = double clap. Refractory lockout prevents machine-gun repeats.

Callbacks (wired by session):
  on_single() → "Yes?" + one hear→execute cycle.
  on_double() → toggle idle/do-not-disturb ("Going quiet." / "I'm back.").

feed() processes int16/float mono blocks synchronously — the stream
callback AND the unit tests use the same path. No hardware in tests.
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("SATURDAY.Claps")

try:
    import sounddevice as sd
    import numpy as np

    _MIC_AVAILABLE = True
except Exception:
    sd = None
    np = None
    _MIC_AVAILABLE = False

SINGLE_WINDOW = (0.18, 0.9)  # seconds between claps = double
REFRACTORY = 1.2
FLOOR_ATTACK = 0.02  # noise floor tracks quiet slowly, never chases claps.


class ClapListener:
    def __init__(self, on_single: Optional[Callable] = None,
                 on_double: Optional[Callable] = None,
                 samplerate: int = 16000, threshold_ratio: float = 8.0):
        self.on_single = on_single
        self.on_double = on_double
        self.samplerate = samplerate
        self.threshold_ratio = threshold_ratio
        self.floor = 60.0
        self.last_hit = 0.0
        self.pending_single = 0.0
        self.lockout_until = 0.0
        self.enabled = False
        self.singles = 0
        self.doubles = 0
        self._stream = None
        self._lock = threading.Lock()

    # -- signal path (shared by stream + tests) ------------------------------
    def feed(self, block) -> Optional[str]:
        """Process one mono block. Returns 'single'|'double'|None."""
        if np is None:
            return None
        x = np.asarray(block, dtype=np.float64).flatten()
        if len(x) == 0:
            return None
        peak = float(abs(x).max())
        rms = float((np.mean(x ** 2)) ** 0.5)
        now = time.time()
        # Noise floor tracks quiet, never chases loud.
        if rms < self.floor * 3:
            self.floor += (rms - self.floor) * FLOOR_ATTACK
            self.floor = max(25.0, self.floor)
        event = None
        if (peak > max(1500.0, self.floor * self.threshold_ratio)
                and now > self.lockout_until):
            with self._lock:
                if self.pending_single and SINGLE_WINDOW[0] <= now - self.pending_single <= SINGLE_WINDOW[1]:
                    event = "double"
                    self.pending_single = 0.0
                    self.lockout_until = now + REFRACTORY
                    self.doubles += 1
                elif not self.pending_single:
                    self.pending_single = now
                # A lone earlier hit that aged out becomes a single.
                elif now - self.pending_single > SINGLE_WINDOW[1]:
                    event = "single"
                    self.pending_single = now
                    self.singles += 1
        else:
            with self._lock:
                if self.pending_single and now - self.pending_single > SINGLE_WINDOW[1]:
                    event = "single"
                    self.pending_single = 0.0
                    self.singles += 1
        if event == "single" and self.on_single:
            self._safe_call(self.on_single)
        elif event == "double" and self.on_double:
            self._safe_call(self.on_double)
        return event

    @staticmethod
    def _safe_call(fn: Callable):
        try:
            fn()
        except Exception as e:
            logger.warning(f"Clap callback failed: {e}")

    # -- live stream -----------------------------------------------------------
    def start(self) -> Dict[str, Any]:
        if not _MIC_AVAILABLE:
            return {"success": False, "error": "mic backend missing"}
        if self._stream:
            return {"success": True, "note": "already listening"}
        try:
            def cb(indata, frames, t, status):
                try:
                    self.feed(indata[:, 0])
                except Exception:
                    pass

            self._stream = sd.InputStream(samplerate=self.samplerate, channels=1,
                                          dtype="float32", blocksize=2048, callback=cb)
            self._stream.start()
            self.enabled = True
            logger.info("Clap listener live.")
            return {"success": True}
        except Exception as e:
            logger.warning(f"Clap stream failed: {e}")
            return {"success": False, "error": str(e)}

    def stop(self):
        self.enabled = False
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
        except Exception:
            pass
        self._stream = None

    def status(self) -> Dict[str, Any]:
        return {"enabled": self.enabled, "live": self._stream is not None,
                "singles": self.singles, "doubles": self.doubles,
                "noise_floor": round(self.floor, 1)}
