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
    "idle":      {"color": (56, 189, 248),  "speed": 0.5, "bands": 1, "width": 2},
    "listening": {"color": (52, 211, 153),  "speed": 2.0, "bands": 2, "width": 2},
    "thinking":  {"color": (167, 139, 250), "speed": 2.6, "bands": 3, "width": 2},
    "speaking":  {"color": (94, 234, 212),  "speed": 3.4, "bands": 3, "width": 2},
    "alert":     {"color": (248, 113, 113), "speed": 4.4, "bands": 4, "width": 2},
    "off":       {"color": (0, 0, 0),       "speed": 0.0, "bands": 0, "width": 0},
}

CORNER = 150          # corner arc size (px)
ARC_GAP = 6           # spacing between concentric corner arcs
EDGE = 3              # inset from the physical screen edge (px)


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
        self.click_through = False  # read-back verified, not assumed
        self._hwnd_ref = 0
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
            root.attributes("-topmost", True)
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.geometry(f"{sw}x{sh}+0+0")
            # PURE overlay, Tk-native path: root AND canvas are pure black,
            # Tk's transparentcolor key removes black itself. No manual
            # layered/colorkey calls — those fight Tk's style management
            # and leave an opaque film over the screen.
            root.attributes("-transparentcolor", "black")
            root.configure(bg="black")
            canvas = tk.Canvas(root, width=sw, height=sh, highlightthickness=0, bd=0,
                               bg="black", background="black")
            canvas.pack()
            self._hwnd_ref = self._hwnd(root)
            self.click_through = self._click_through(root) and self.verify_click_through()
            if not self.click_through:
                logger.warning("Edge glow: click-through NOT verified — overlay may block input.")
            t = 0.0
            frames = 0
            while not self._stop.is_set():
                state = self.current()
                cfg = STATES.get(state, STATES["idle"])
                canvas.delete("all")
                frames += 1
                # Re-assert click-through: Tk can reset ex-style on redraws.
                if frames % 24 == 0:
                    try:
                        self.click_through = (self._click_through(root)
                                              and self.verify_click_through())
                    except Exception:
                        pass
                if cfg["bands"]:
                    t += 0.09
                    brightness = pulse_brightness(state, t)
                    # Thin full-perimeter lines (dim) + bright corner arcs:
                    # reads as edge glow, stays 2px thin, screen untouched.
                    line_col = band_colors(cfg["color"], 1, t * cfg["speed"],
                                           brightness * 0.45)[0]
                    m = EDGE
                    canvas.create_line(m, m, sw - m, m, fill=line_col, width=1)
                    canvas.create_line(m, sh - m, sw - m, sh - m, fill=line_col, width=1)
                    canvas.create_line(m, m, m, sh - m, fill=line_col, width=1)
                    canvas.create_line(sw - m, m, sw - m, sh - m, fill=line_col, width=1)
                    for i in range(cfg["bands"]):
                        col = band_colors(cfg["color"], 1, t * cfg["speed"],
                                          brightness * (1.0 - 0.22 * i))[0]
                        inset = EDGE + i * ARC_GAP
                        r = CORNER - i * ARC_GAP
                        if r <= 6:
                            break
                        w = cfg["width"]
                        # Four corner arcs only — screen stays fully readable.
                        canvas.create_arc(inset, inset, inset + 2 * r, inset + 2 * r,
                                          start=0, extent=90, style="arc",
                                          outline=col, width=w)
                        canvas.create_arc(sw - inset - 2 * r, inset,
                                          sw - inset, inset + 2 * r,
                                          start=90, extent=90, style="arc",
                                          outline=col, width=w)
                        canvas.create_arc(sw - inset - 2 * r, sh - inset - 2 * r,
                                          sw - inset, sh - inset,
                                          start=180, extent=90, style="arc",
                                          outline=col, width=w)
                        canvas.create_arc(inset, sh - inset - 2 * r,
                                          inset + 2 * r, sh - inset,
                                          start=270, extent=90, style="arc",
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
    def _hwnd(root) -> int:
        """A Tk toplevel's winfo_id IS its HWND (GetParent returns 0/desktop
        and silently targets the wrong window — the old click-block bug)."""
        try:
            return int(root.winfo_id())
        except Exception:
            return 0

    def verify_click_through(self) -> bool:
        """Read back WS_EX_TRANSPARENT — True only if clicks REALLY pass."""
        try:
            import ctypes
            hwnd = self._hwnd_ref or 0
            if not hwnd:
                return False
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            return bool(ex & 0x20)
        except Exception:
            return False

    @staticmethod
    def _make_transparent(root) -> bool:
        """Layered window: black alpha 0 → nothing shows except what we draw."""
        try:
            import ctypes
            hwnd = EdgeGlow._hwnd(root)
            if not hwnd:
                return False
            gwl, layered, transparent = -20, 0x00080000, 0x00000020
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, gwl)
            ok = ctypes.windll.user32.SetWindowLongW(hwnd, gwl, ex | layered | transparent)
            if not ok:
                return False
            # LWA_COLORKEY = 1, key = 1 (near-black canvas background).
            return bool(ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 1, 0, 1))
        except Exception:
            return False

    @staticmethod
    def _click_through(root) -> bool:
        """Let clicks fall through to windows beneath (Windows, ctypes)."""
        try:
            import ctypes

            hwnd = EdgeGlow._hwnd(root)
            if not hwnd:
                return False
            gwl = -20
            layered, transparent = 0x80000, 0x20
            cur = ctypes.windll.user32.GetWindowLongW(hwnd, gwl)
            ok = ctypes.windll.user32.SetWindowLongW(hwnd, gwl, cur | layered | transparent)
            return bool(ok)
        except Exception as e:
            logger.debug(f"Click-through unavailable: {e}")
            return False
