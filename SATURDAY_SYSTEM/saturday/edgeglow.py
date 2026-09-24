"""SATURDAY Edge Glow — Gemini/Siri-style living screen border.

Always-on-top, click-through fullscreen overlay: only a glowing animated
border is visible; everything else is transparent. It breathes with
SATURDAY's state — idle shimmer, listening pulse, thinking sweep,
speaking wave, alert flash, off in quiet mode.

Tech: stdlib tkinter + ctypes (WS_EX_TRANSPARENT click-through). No new
dependencies, daemon thread, ~12fps redraw of a dozen rectangles (trivial
CPU). Any failure (RDP, headless, no tkinter) degrades to silent off —
never a crash, never a stuck window (failsafe stop() destroys it).
"""

import logging
import math
import threading
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger("SATURDAY.Glow")

try:
    import tkinter as tk

    _TK_AVAILABLE = True
except Exception:
    tk = None
    _TK_AVAILABLE = False

STATES: Dict[str, Dict] = {
    "idle":      {"color": (34, 211, 238),  "speed": 0.6, "width": 3,  "bands": 10},
    "listening": {"color": (52, 211, 153),  "speed": 2.2, "width": 6,  "bands": 14},
    "thinking":  {"color": (167, 139, 250), "speed": 3.0, "width": 5,  "bands": 14},
    "speaking":  {"color": (94, 234, 212),  "speed": 4.0, "width": 5,  "bands": 12},
    "alert":     {"color": (248, 113, 113), "speed": 5.0, "width": 7,  "bands": 14},
    "off":       {"color": (0, 0, 0),       "speed": 0.0, "width": 0,  "bands": 0},
}


def band_colors(base: Tuple[int, int, int], bands: int, phase: float,
                brightness: float = 1.0):
    """Per-band RGB hex strings: base fading outward + traveling wave."""
    out = []
    for i in range(max(1, bands)):
        fade = 1.0 - (i / max(1, bands))
        wave = 0.55 + 0.45 * math.sin(phase - i * 0.55)
        k = max(0.0, min(1.0, fade * wave * brightness))
        r, g, b = (int(c * k) for c in base)
        out.append(f"#{r:02x}{g:02x}{b:02x}")
    return out


def pulse_brightness(state: str, t: float) -> float:
    speed = STATES.get(state, STATES["idle"])["speed"]
    return 0.72 + 0.28 * math.sin(t * speed * 2.0)


class EdgeGlow:
    def __init__(self):
        self.state = "idle"
        self._until = 0.0  # temporary pulse expiry
        self._base = "idle"
        self.enabled = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    @staticmethod
    def available() -> bool:
        return _TK_AVAILABLE

    # -- state ---------------------------------------------------------------
    def set_state(self, state: str):
        if state in STATES:
            with self._lock:
                self.state = state
                self._base = state
                self._until = 0.0

    def pulse(self, state: str, seconds: float = 3.0):
        """Temporary state, then falls back (speaking/listening blips)."""
        if state in STATES and state != "off":
            with self._lock:
                self.state = state
                self._until = time.time() + seconds

    def current(self) -> str:
        with self._lock:
            if self._until and time.time() > self._until:
                self.state = self._base
                self._until = 0.0
            return self.state

    # -- window ----------------------------------------------------------------
    def start(self) -> Dict:
        if self._thread and self._thread.is_alive():
            return {"success": True, "note": "already glowing"}
        if not _TK_AVAILABLE:
            return {"success": False, "error": "tkinter missing"}
        self._stop.clear()
        self.enabled = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="edge-glow")
        self._thread.start()
        return {"success": True}

    def stop(self):
        self.enabled = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=4.0)
        self._thread = None

    def _run(self):
        try:
            root = tk.Tk()
        except Exception as e:
            logger.warning(f"Edge glow: no display ({e})")
            self.enabled = False
            return
        try:
            root.overrideredirect(True)
            root.attributes("-topmost", True, "-transparentcolor", "black")
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.geometry(f"{sw}x{sh}+0+0")
            root.configure(bg="black")
            self._click_through(root)
            canvas = tk.Canvas(root, width=sw, height=sh, bg="black",
                               highlightthickness=0, bd=0)
            canvas.pack()
            t = 0.0
            gap = 7
            while not self._stop.is_set():
                state = self.current()
                cfg = STATES.get(state, STATES["idle"])
                canvas.delete("all")
                if cfg["bands"]:
                    t += 0.09
                    colors = band_colors(cfg["color"], cfg["bands"], t * cfg["speed"],
                                         pulse_brightness(state, t))
                    w = cfg["width"]
                    for i, col in enumerate(colors):
                        inset = i * gap
                        canvas.create_rectangle(
                            inset, inset, sw - inset, sh - inset,
                            outline=col, width=w)
                try:
                    root.update_idletasks()
                    root.update()
                except Exception:
                    break
                time.sleep(1.0 / 12.0)
        except Exception as e:
            logger.warning(f"Edge glow loop ended: {e}")
        finally:
            try:
                root.destroy()
            except Exception:
                pass
            logger.info("Edge glow off.")

    @staticmethod
    def _click_through(root) -> bool:
        """Let clicks fall through to windows beneath (Windows, ctypes)."""
        try:
            import ctypes

            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            gwl = -20
            layered, transparent = 0x80000, 0x20
            cur = ctypes.windll.user32.GetWindowLongW(hwnd, gwl)
            ctypes.windll.user32.SetWindowLongW(hwnd, gwl, cur | layered | transparent)
            return True
        except Exception as e:
            logger.debug(f"Click-through unavailable: {e}")
            return False
