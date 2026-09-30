"""SATURDAY Screen Operator — offline GUI automation.

Sense → Understand → Act → Verify loop for using any on-screen app
(browser Gmail, socials, system dialogs) with zero API credentials.

- SENSE  : screenshot() captures the screen to a file for review.
- UNDERSTAND: describe() returns screenshot metadata; the caller (agent or
  user) views the image and decides coordinates.
- ACT    : open_app/open_url/click/type/press/hotkey/scroll drive the UI.
- VERIFY : pixel_change() measures before/after difference to confirm effect.

Safety model:
- pyautogui FAILSAFE is always ON (slam mouse to a corner aborts motion).
- click/type/press/hotkey/open REQUIRE confirm=True per call. Interactive
  callers (CLI, local voice) pass confirm=True; remote callers (realtime
  bridge) pass confirm=False and are refused. There is no ambient trust.
- Typed text is NEVER logged or stored — history keeps char counts only.
- Clicks are bounds-checked against the real screen size.
- Everything is local (pyautogui + Pillow). No network, no credentials.

All methods return {"success": bool, ...} dicts; they never raise on
expected failures (missing backend, bad input, refused confirmation).
"""

import logging
import os
import tempfile
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Screen")


def _ensure_dpi_aware() -> str:
    """One coordinate system everywhere: make THIS process per-monitor
    DPI-aware at startup so pyautogui pixels == real pixels. Verified:
    GetProcessDpiAwareness 0→2, click lands exactly at 100% scale."""
    try:
        import ctypes as _ct

        try:
            got = _ct.c_int()
            _ct.windll.shcore.GetProcessDpiAwareness(None, _ct.byref(got))
            before = int(got.value)
        except Exception:
            before = -1
        try:
            _ct.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
        try:
            _ct.windll.shcore.GetProcessDpiAwareness(None, _ct.byref(got))
            after = int(got.value)
        except Exception:
            after = before
        logger.info(f"DPI awareness {before}→{after} (2=per-monitor, pixels are real)")
        return f"{before}->{after}"
    except Exception as e:
        logger.debug(f"DPI awareness n/a: {e}")
        return "n/a"


_DPI_STATE = _ensure_dpi_aware()


def dpi_state() -> str:
    return _DPI_STATE


# -- D: paths: C: is ~95% full, screenshots/audit never touch it -----------
def _d_tmp() -> Path:
    base = Path(os.getenv("SATURDAY_D_TMP", "D:/SATURDAY_TEMP"))
    try:
        (base / "screens").mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base


def _shot_path() -> str:
    try:
        return str(_d_tmp() / "screens" / f"saturday_see_{int(time.time())}.png")
    except Exception:
        return str(Path(tempfile.gettempdir()) / f"saturday_see_{int(time.time())}.png")


AUDIT_LOG = _d_tmp() / "screen_audit.jsonl"


def _append_audit(entry: Dict[str, Any]) -> None:
    try:
        import json as _j

        with open(AUDIT_LOG, "a", encoding="utf-8") as fh:
            fh.write(_j.dumps(entry) + "\n")
    except Exception:
        pass


class _Indicator:
    """Visible on-screen banner while SATURDAY drives the computer
    (tkinter topmost pill; falls back to console title + log line)."""

    def __init__(self, text: str = "SATURDAY CONTROLLING — Ctrl+Alt+Shift+X stops"):
        self.text = text
        self.root = None

    def __enter__(self):
        try:
            import tkinter as _tk

            self.root = _tk.Tk()
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", 0.92)
            lbl = _tk.Label(self.root, text="  " + self.text + "  ",
                            bg="#7f1d1d", fg="white",
                            font=("Segoe UI", 11, "bold"))
            lbl.pack()
            self.root.geometry(f"+{self.root.winfo_screenwidth() - 560}+8")
            self.root.update()
        except Exception:
            self.root = None
        try:
            import ctypes as _ct

            _ct.windll.kernel32.SetConsoleTitleW("SATURDAY *CONTROLLING* (Ctrl+Alt+Shift+X stops)")
        except Exception:
            pass
        logger.warning("INDICATOR ON — SATURDAY is driving the screen")
        return self

    def __exit__(self, *a):
        try:
            if self.root is not None:
                self.root.destroy()
        except Exception:
            pass
        try:
            import ctypes as _ct

            _ct.windll.kernel32.SetConsoleTitleW("SATURDAY")
        except Exception:
            pass
        logger.warning("INDICATOR OFF")
        return False

try:
    import pyautogui

    pyautogui.FAILSAFE = True
    _PYAUTOGUI_AVAILABLE = True
    _IMPORT_ERROR = ""
except Exception as e:  # pragma: no cover - backend missing
    pyautogui = None
    _PYAUTOGUI_AVAILABLE = False
    _IMPORT_ERROR = str(e)

try:
    from PIL import Image, ImageChops, ImageStat

    _PIL_AVAILABLE = True
except Exception:  # pragma: no cover - backend missing
    Image = ImageChops = ImageStat = None
    _PIL_AVAILABLE = False

try:
    import pytesseract
    from pytesseract import Output as _TessOutput

    try:
        pytesseract.get_tesseract_version()  # needs the Tesseract binary, not just the wrapper
        _OCR_AVAILABLE = True
        _OCR_ERROR = ""
    except Exception:
        # Retry against the standard Windows install location (PATH often misses it).
        _STD_TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        try:
            import os as _os

            if _os.path.exists(_STD_TESS):
                pytesseract.pytesseract.tesseract_cmd = _STD_TESS
            pytesseract.get_tesseract_version()
            _OCR_AVAILABLE = True
            _OCR_ERROR = ""
        except Exception as e:
            _OCR_AVAILABLE = False
            _OCR_ERROR = f"Tesseract binary missing ({e}). Install it: winget install UB-Mannheim.TesseractOCR"
except Exception as e:  # pragma: no cover - wrapper missing
    pytesseract = None
    _TessOutput = None
    _OCR_AVAILABLE = False
    _OCR_ERROR = f"pytesseract not installed ({e}). Run: pip install pytesseract + Tesseract binary"


def ocr_available() -> bool:
    return _OCR_AVAILABLE


# Shortcuts so `open gmail` does the obvious thing without credentials.
URL_SHORTCUTS = {
    "gmail": "https://mail.google.com",
    "mail": "https://mail.google.com",
    "calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com",
    "youtube": "https://www.youtube.com",
    "whatsapp": "https://web.whatsapp.com",
}

# Keys that can destroy data or dismiss dialogs blindly get an extra nudge
# in the refusal message so callers think twice.
RISKY_KEYS = {"delete", "backspace"}


def backend_available() -> bool:
    return _PYAUTOGUI_AVAILABLE


class ScreenOperator:
    """Offline screen sense/act/verify driver with per-call confirmation."""

    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def indicator(self, text: str = "SATURDAY CONTROLLING — Ctrl+Alt+Shift+X stops"):
        return _Indicator(text)

    # -- internals -----------------------------------------------------
    def _err(self, reason: str) -> Dict[str, Any]:
        return {"success": False, "error": reason}

    def _need_backend(self) -> Optional[Dict[str, Any]]:
        if not _PYAUTOGUI_AVAILABLE:
            return self._err(f"pyautogui unavailable ({_IMPORT_ERROR}); pip install pyautogui")
        return None

    def _audit(self, action: str, detail: str, method: str = "",
               target: str = "", result: str = "") -> None:
        entry = {"action": action, "method": method, "target": target,
                 "result": result, "detail": detail, "at": time.time()}
        self.history.append(entry)
        self.history = self.history[-200:]  # bounded: safe for months of use
        _append_audit(entry)  # D: JSONL audit: every action (ts, method, target, result)
        logger.info(f"Screen action: {action} via {method or '?'} → {result or '?'} ({detail})")

    def _gated(self, action: str, confirm: bool) -> Optional[Dict[str, Any]]:
        if not confirm:
            return self._err(
                f"'{action}' requires explicit confirmation (confirm=True). "
                "Refusing: remote/untrusted callers may not drive the screen."
            )
        return None

    # -- windows state (focus / elevation / settle) ----------------------
    @staticmethod
    def active_title() -> str:
        try:
            import pygetwindow as _gw

            return str(_gw.getActiveWindowTitle() or "")
        except Exception:
            return ""

    def _ensure_focus(self, want: str = "", retries: int = 2) -> Dict[str, Any]:
        """Confirm the target window is focused before clicking/typing.
        Retries after a short wait; warns (never silently proceeds blind)."""
        for attempt in range(retries + 1):
            title = self.active_title()
            if want and want.lower() in title.lower():
                return {"success": True, "title": title}
            if not want and title:
                return {"success": True, "title": title}
            if attempt < retries:
                self.focus_window(want) if want else time.sleep(0.5)
        title = self.active_title()
        return {"success": bool(title) or not want, "title": title,
                "warning": f"focus unconfirmed (want {want!r}, active {title!r})"}

    def focus_window(self, title_part: str) -> Dict[str, Any]:
        try:
            import pygetwindow as _gw

            cands = [w for w in _gw.getAllWindows() if title_part.lower() in (w.title or "").lower()]
            if not cands:
                return self._err(f"No window matching {title_part!r} to focus.")
            # Prefer exact title, then title-start, then first Z-order —
            # never blindly grab an error dialog that merely contains the name.
            exact = [w for w in cands if (w.title or "").lower() == title_part.lower()]
            starts = [w for w in cands if (w.title or "").lower().startswith(title_part.lower())]
            w = (exact or starts or cands)[0]
            try:
                if w.isMinimized:
                    w.restore()
            except Exception:
                pass
            w.activate()
            time.sleep(0.4)
            now = self.active_title()
            ok = title_part.lower() in now.lower()
            self._audit("focus", f"{title_part} -> {now!r}",
                        method="pygetwindow", target=title_part,
                        result="ok" if ok else "unconfirmed")
            return {"success": ok, "title": now, "method": "pygetwindow"}
        except Exception as e:
            return self._err(f"focus failed: {e}")

    @staticmethod
    def foreground_is_elevated() -> Optional[bool]:
        """True = foreground window runs as admin/UAC: a normal process
        CANNOT drive it. Detect and say so loudly, never fail silently."""
        try:
            import ctypes as _ct

            u32 = _ct.windll.user32
            hwnd = u32.GetForegroundWindow()
            if not hwnd:
                return None
            pid = _ct.c_ulong()
            u32.GetWindowThreadProcessId(hwnd, _ct.byref(pid))
            proc = _ct.windll.kernel32.OpenProcess(0x0400, False, pid.value)  # QUERY_INFORMATION
            if not proc:
                return None
            try:
                tok = _ct.c_void_p()
                if not _ct.windll.advapi32.OpenProcessToken(proc, 0x0008, _ct.byref(tok)):
                    return None
                try:
                    elev = _ct.c_int()
                    size = _ct.c_ulong(4)
                    rc = _ct.windll.advapi32.GetTokenInformation(
                        tok, 20, _ct.byref(elev), 4, _ct.byref(size))  # TokenElevation
                    return bool(rc and elev.value) if rc else None
                finally:
                    _ct.windll.kernel32.CloseHandle(tok)
            finally:
                _ct.windll.kernel32.CloseHandle(proc)
        except Exception:
            return None

    def wait_for_change(self, before_path: str, timeout: float = 8.0,
                        threshold: float = 0.002) -> Dict[str, Any]:
        """Poll for UI settle (not fixed sleeps): screenshot until pixels
        move past `threshold` or timeout. Stable screen → changed_ratio ~0."""
        deadline = time.time() + max(1.0, timeout)
        last = None
        while time.time() < deadline:
            shot = self.screenshot()
            if not shot.get("success"):
                time.sleep(0.5)
                continue
            res = self.pixel_change(before_path, shot["path"])
            ratio = float(res.get("changed_ratio", 0.0))
            last = {"ratio": ratio, "after": shot["path"]}
            if ratio >= threshold:
                self._audit("wait_settle", f"changed {ratio:.4f}",
                            method="poll", target=before_path, result="changed")
                return {"success": True, "changed_ratio": ratio, "after": shot["path"],
                        "method": "poll"}
            time.sleep(0.5)
        self._audit("wait_settle", f"stable {last['ratio']:.4f}" if last else "no shot",
                    method="poll", target=before_path, result="stable-timeout")
        out = {"success": True, "stable": True, "method": "poll"}
        if last:
            out.update(changed_ratio=last["ratio"], after=last["after"])
        return out

    # -- SENSE ---------------------------------------------------------
    def screen_size(self) -> Dict[str, Any]:
        missing = self._need_backend()
        if missing:
            return missing
        try:
            w, h = pyautogui.size()
            return {"success": True, "width": int(w), "height": int(h)}
        except Exception as e:
            logger.warning(f"screen_size failed: {e}")
            return self._err(str(e))

    def screenshot(self, path: Optional[str] = None) -> Dict[str, Any]:
        missing = self._need_backend()
        if missing:
            return missing
        try:
            if not path:
                path = _shot_path()
            shot = pyautogui.screenshot()
            shot.save(path)
            w, h = shot.size
            self._audit("screenshot", f"{path} [{w}x{h}]",
                        method="pyautogui", target="screen", result=f"{w}x{h}")
            return {"success": True, "path": path, "width": w, "height": h,
                    "method": "screenshot"}
        except Exception as e:
            logger.warning(f"screenshot failed: {e}")
            return self._err(str(e))

    def describe(self, path: str) -> Dict[str, Any]:
        """Metadata handoff for vision: view the file at `path`, then act."""
        try:
            p = Path(path)
            if not p.exists():
                return self._err(f"No such screenshot: {path}")
            info = {"success": True, "path": str(p), "bytes": p.stat().st_size}
            if _PIL_AVAILABLE:
                with Image.open(p) as img:
                    info["width"], info["height"] = img.size
            return info
        except Exception as e:
            return self._err(str(e))

    # -- ACT -----------------------------------------------------------
    def open_url(self, url: str, confirm: bool = False) -> Dict[str, Any]:
        gated = self._gated("open_url", confirm)
        if gated:
            return gated
        target = (url or "").strip()
        if not target:
            return self._err("Empty URL.")
        lowered = target.lower()
        if lowered in URL_SHORTCUTS:
            target = URL_SHORTCUTS[lowered]
        elif "://" not in target:
            if " " in target or "." not in target:
                return self._err(f"Not a URL: {target!r}. Use 'open <app name>' for apps.")
            target = "https://" + target
        try:
            webbrowser.open(target)
            self._audit("open_url", target, method="browser", target=target, result="opened")
            return {"success": True, "url": target}
        except Exception as e:
            logger.warning(f"open_url failed: {e}")
            return self._err(str(e))

    # -- ACT: control ladder -------------------------------------------
    # 1. Direct API/CLI/URL/file ops  2. Windows UI Automation
    # 3. Keyboard shortcuts/hotkeys    4. OCR/vision click (fallback only)
    # Every action result names its method; audit JSONL on D: keeps all.
    def launch_direct(self, app_name: str, confirm: bool = False) -> Dict[str, Any]:
        """Ladder 1: start an app without touching the keyboard (Start-Process
        / startfile). Fastest and most reliable when it works."""
        gated = self._gated("launch_direct", confirm)
        if gated:
            return gated
        import subprocess as _sp

        app_name = (app_name or "").strip().strip('"')
        if not app_name:
            return self._err("Empty app name.")
        if len(app_name) > 120:
            return self._err("App name too long.")
        try:
            before = self.screenshot()
            _sp.Popen(["powershell", "-NoProfile", "-Command",
                       "Start-Process", app_name],
                      stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
            settled = self.wait_for_change(before["path"], timeout=8.0) if before.get("success") else {}
            self._audit("launch_direct", app_name, method="start-process",
                        target=app_name, result="launched")
            out = {"success": True, "app": app_name, "method": "start-process"}
            out.update({k: v for k, v in settled.items() if k in ("changed_ratio", "stable")})
            return out
        except Exception as e:
            logger.warning(f"launch_direct failed: {e}")
            return self._err(str(e))

    def uia_find(self, title_part: str, control_name: str = "",
                 timeout: float = 10.0) -> Dict[str, Any]:
        """Ladder 2: find a control by name/role via Windows UI Automation
        (pywinauto). Honest 'unavailable' when the backend is missing."""
        try:
            from pywinauto import Desktop as _Desk
        except Exception as e:
            return self._err(f"UI Automation unavailable (pip install pywinauto): {e}")
        try:
            wins = [w for w in _Desk(backend="uia").windows()
                    if title_part.lower() in (w.window_text() or "").lower()]
            if not wins:
                wins = [w for w in _Desk(backend="win32").windows()
                        if title_part.lower() in (w.window_text() or "").lower()]
            if not wins:
                return self._err(f"No window matching {title_part!r} for UIA.")
            win = wins[0]
            info = {"success": True, "window": win.window_text(),
                    "method": "uia", "handle": int(win.handle)}
            if control_name:
                try:
                    ctrl = win.child_window(title=control_name, control_type="Button")
                    if not ctrl.exists(timeout=timeout):
                        ctrl = win.descendants(title=control_name)
                        ctrl = ctrl[0] if ctrl else None
                    if ctrl is None or (hasattr(ctrl, "exists") and not ctrl.exists()):
                        return self._err(f"Control {control_name!r} not found in {win.window_text()!r}.")
                    info["control"] = control_name
                    info["rect"] = str(getattr(ctrl, "rectangle", lambda: "?")())
                except Exception as e:
                    return self._err(f"UIA control lookup failed: {e}")
            self._audit("uia_find", f"{title_part}/{control_name or '*'}",
                        method="uia", target=title_part, result="found")
            return info
        except Exception as e:
            return self._err(f"UIA failed: {e}")

    def uia_click(self, title_part: str, control_name: str,
                  confirm: bool = False) -> Dict[str, Any]:
        """Ladder 2 act: click a named control (button/menu) by role, no OCR."""
        gated = self._gated("uia_click", confirm)
        if gated:
            return gated
        try:
            from pywinauto import Desktop as _Desk
        except Exception as e:
            return self._err(f"UI Automation unavailable (pip install pywinauto): {e}")
        try:
            wins = [w for w in _Desk(backend="uia").windows()
                    if title_part.lower() in (w.window_text() or "").lower()]
            if not wins:
                return self._err(f"No window matching {title_part!r} for UIA.")
            win = wins[0]
            try:
                win.set_focus()
            except Exception:
                pass
            ctrls = win.descendants(title=control_name)
            if not ctrls:
                return self._err(f"Control {control_name!r} not found in {win.window_text()!r}.")
            ctrls[0].click_input()
            self._audit("uia_click", control_name, method="uia",
                        target=f"{title_part}/{control_name}", result="clicked")
            return {"success": True, "control": control_name,
                    "window": win.window_text(), "method": "uia"}
        except Exception as e:
            logger.warning(f"uia_click failed: {e}")
            return self._err(str(e))

    def open_app(self, app_name: str, confirm: bool = False) -> Dict[str, Any]:
        """Open an app via the ladder: direct launch first, Start-menu
        typing as fallback. Waits for UI settle by polling, not fixed sleeps."""
        gated = self._gated("open_app", confirm)
        if gated:
            return gated
        app_name = (app_name or "").strip()
        if not app_name:
            return self._err("Empty app name.")
        direct = self.launch_direct(app_name, confirm=confirm)
        if direct.get("success"):
            direct["app"] = app_name
            return direct
        missing = self._need_backend()
        if missing:
            return missing
        try:
            before = self.screenshot()
            pyautogui.press("win")
            time.sleep(0.5)
            pyautogui.write(app_name, interval=0.05)
            time.sleep(0.5)
            pyautogui.press("enter")
            if before.get("success"):
                self.wait_for_change(before["path"], timeout=8.0)
            self._audit("open_app", app_name, method="start-menu",
                        target=app_name, result="launched")
            return {"success": True, "app": app_name, "method": "start-menu"}
        except Exception as e:
            logger.warning(f"open_app failed: {e}")
            return self._err(str(e))

    def file_write(self, path: str, content: str, confirm: bool = False) -> Dict[str, Any]:
        """Ladder 1: create/overwrite a text file with Python file ops —
        no Notepad needed. Restricted to D: (C: is full and off-limits)."""
        gated = self._gated("file_write", confirm)
        if gated:
            return gated
        try:
            p = Path(os.path.expandvars(str(path or ""))).resolve()
        except Exception:
            return self._err("Bad path.")
        if not str(p).upper().startswith("D:"):
            return self._err(f"Refusing: files go on D: only (got {p}).")
        if len(content or "") > 200000:
            return self._err("Content too long (200k limit).")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content or "", encoding="utf-8")
            self._audit("file_write", f"{p} ({len(content or '')} chars)",
                        method="direct-fs", target=str(p), result="written")
            return {"success": True, "path": str(p), "chars": len(content or ""),
                    "method": "direct-fs"}
        except Exception as e:
            return self._err(str(e))

    def click(self, x: int, y: int, confirm: bool = False,
              window: str = "") -> Dict[str, Any]:
        gated = self._gated("click", confirm)
        if gated:
            return gated
        missing = self._need_backend()
        if missing:
            return missing
        try:
            x, y = int(x), int(y)
        except (TypeError, ValueError):
            return self._err("Coordinates must be integers. Usage: click <x> <y>")
        size = self.screen_size()
        if size.get("success"):
            if not (0 <= x < size["width"] and 0 <= y < size["height"]):
                return self._err(
                    f"({x},{y}) outside screen {size['width']}x{size['height']}. "
                    "Run 'see' first and use on-screen coordinates."
                )
        elev = self.foreground_is_elevated()
        if elev:
            msg = ("Refusing: foreground window is ELEVATED (admin/UAC) — a normal "
                   "process cannot drive it. Click it yourself or restart SATURDAY as admin.")
            self._audit("click", msg, method="pyautogui",
                        target=f"({x},{y})", result="refused-elevated")
            return self._err(msg)
        focus = self._ensure_focus(window) if window else {"success": True, "title": self.active_title()}
        try:
            with self.indicator():
                pyautogui.click(x, y)
            warn = focus.get("warning")
            self._audit("click", f"({x},{y})" + (f" [{warn}]" if warn else ""),
                        method="pyautogui", target=f"({x},{y})", result="clicked")
            out = {"success": True, "x": x, "y": y, "method": "pyautogui"}
            if warn:
                out["warning"] = warn
            return out
        except Exception as e:
            logger.warning(f"click failed: {e}")
            return self._err(str(e))

    SENSITIVE_TITLE_BITS = ("login", "log in", "sign in", "password", "checkout",
                            "payment", "pay now", "card number", "cvv")

    def type_text(self, text: str, confirm: bool = False, interval: float = 0.02,
                  window: str = "") -> Dict[str, Any]:
        gated = self._gated("type", confirm)
        if gated:
            return gated
        missing = self._need_backend()
        if missing:
            return missing
        if not text:
            return self._err("Nothing to type.")
        if len(text) > 4000:
            return self._err("Text too long (4000 char limit per call).")
        title = self.active_title()
        low = title.lower()
        if any(k in low for k in self.SENSITIVE_TITLE_BITS):
            msg = (f"Handing off to you: {title!r} looks like a login/payment page. "
                   "I never type passwords or handle payment fields — take the keyboard.")
            self._audit("type", msg, method="refused",
                        target=title, result="refused-sensitive")
            return {"success": False, "error": msg, "handoff": True}
        elev = self.foreground_is_elevated()
        if elev:
            msg = ("Refusing: foreground window is ELEVATED (admin/UAC). "
                   "Type there yourself or restart SATURDAY as admin.")
            self._audit("type", msg, method="pyautogui",
                        target=title, result="refused-elevated")
            return self._err(msg)
        focus = self._ensure_focus(window) if window else {"success": True, "title": title}
        try:
            with self.indicator():
                pyautogui.write(text, interval=interval)
            # Deliberately log/store length only — never the content.
            warn = focus.get("warning")
            self._audit("type", f"{len(text)} chars" + (f" [{warn}]" if warn else ""),
                        method="pyautogui", target=title, result="typed")
            out = {"success": True, "chars": len(text), "method": "pyautogui"}
            if warn:
                out["warning"] = warn
            return out
        except Exception as e:
            logger.warning(f"type failed: {e}")
            return self._err(str(e))

    def press(self, key: str, confirm: bool = False) -> Dict[str, Any]:
        key = (key or "").strip().lower()
        gated = self._gated("press", confirm)
        if gated:
            if key in RISKY_KEYS:
                gated["error"] += " This key can delete data — confirm you mean it."
            return gated
        missing = self._need_backend()
        if missing:
            return missing
        if not key:
            return self._err("Empty key. Usage: press <key> (e.g. press enter)")
        try:
            valid = {k.lower() for k in getattr(pyautogui, "KEYBOARD_KEYS", [key])}
        except Exception:
            valid = {key}
        if key not in valid:
            return self._err(f"Unknown key: {key!r}")
        try:
            pyautogui.press(key)
            self._audit("press", key, method="pyautogui", target=key, result="pressed")
            return {"success": True, "key": key}
        except Exception as e:
            logger.warning(f"press failed: {e}")
            return self._err(str(e))

    def hotkey(self, keys: List[str], confirm: bool = False) -> Dict[str, Any]:
        gated = self._gated("hotkey", confirm)
        if gated:
            return gated
        missing = self._need_backend()
        if missing:
            return missing
        keys = [str(k).strip().lower() for k in (keys or []) if str(k).strip()]
        if not 1 <= len(keys) <= 4:
            return self._err("Usage: hotkey <key1> <key2> [key3]. Example: hotkey ctrl t")
        try:
            pyautogui.hotkey(*keys)
            self._audit("hotkey", "+".join(keys), method="hotkey", target="+".join(keys), result="sent")
            return {"success": True, "keys": keys}
        except Exception as e:
            logger.warning(f"hotkey failed: {e}")
            return self._err(str(e))

    def scroll(self, amount: int, confirm: bool = False) -> Dict[str, Any]:
        gated = self._gated("scroll", confirm)
        if gated:
            return gated
        missing = self._need_backend()
        if missing:
            return missing
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            return self._err("Amount must be an integer. Usage: scroll <amount>")
        if abs(amount) > 50:
            return self._err("Scroll clamped to ±50 per call.")
        try:
            pyautogui.scroll(amount)
            self._audit("scroll", str(amount), method="pyautogui", target=str(amount), result="scrolled")
            return {"success": True, "amount": amount}
        except Exception as e:
            logger.warning(f"scroll failed: {e}")
            return self._err(str(e))

    # -- READ (self-reading: OCR text + word boxes, fully local) ----
    def read_screen(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Read text off the screen. Returns text plus per-word boxes so
        SATURDAY can ground actions ('click the word Compose') by itself."""
        if not _OCR_AVAILABLE:
            return self._err(_OCR_ERROR)
        try:
            if path is None:
                shot = self.screenshot()
                if not shot.get("success"):
                    return shot
                path = shot["path"]
            with Image.open(path) as img:
                data = pytesseract.image_to_data(img, output_type=_TessOutput.DICT)
            words = []
            for i, word in enumerate(data.get("text", [])):
                word = (word or "").strip()
                if not word:
                    continue
                try:
                    conf = float(data["conf"][i])
                except (ValueError, TypeError):
                    conf = -1.0
                if conf < 30:
                    continue
                words.append({
                    "text": word,
                    "x": int(data["left"][i]), "y": int(data["top"][i]),
                    "w": int(data["width"][i]), "h": int(data["height"][i]),
                    "conf": round(conf, 1),
                })
            text = " ".join(w["text"] for w in words)
            self._audit("read", f"{len(words)} words from {path}", method="ocr", target=str(path), result=f"{len(words)} words")
            return {"success": True, "path": path, "text": text, "words": words}
        except Exception as e:
            logger.warning(f"read_screen failed: {e}")
            return self._err(str(e))

    def click_text(self, phrase: str, confirm: bool = False) -> Dict[str, Any]:
        """Find on-screen text and click its center. No coordinates needed."""
        gated = self._gated("click_text", confirm)
        if gated:
            return gated
        phrase = (phrase or "").strip().lower()
        if not phrase:
            return self._err("Usage: clicktext <word on screen>. Example: clicktext Compose")
        seen = self.read_screen()
        if not seen.get("success"):
            return seen
        target_words = phrase.split()
        best = None
        for w in seen.get("words", []):
            if w["text"].lower() in target_words or phrase in w["text"].lower():
                best = w
                break
        if not best:
            full = seen.get("text", "")[:300]
            return self._err(f"'{phrase}' not found on screen. Visible starts: {full!r}")
        cx, cy = best["x"] + best["w"] // 2, best["y"] + best["h"] // 2
        return self.click(cx, cy, confirm=confirm)

    # -- VERIFY --------------------------------------------------------
    def pixel_change(self, before_path: str, after_path: Optional[str] = None) -> Dict[str, Any]:
        """0.0 (identical) → 1.0 (fully changed) between two screenshots."""
        if not _PIL_AVAILABLE:
            return self._err("Pillow unavailable; pip install pillow")
        try:
            if after_path is None:
                shot = self.screenshot()
                if not shot.get("success"):
                    return shot
                after_path = shot["path"]
            with Image.open(before_path) as a, Image.open(after_path) as b:
                a_gray = a.convert("L")
                b_gray = b.convert("L")
                if a_gray.size != b_gray.size:
                    b_gray = b_gray.resize(a_gray.size)
                diff = ImageChops.difference(a_gray, b_gray)
                ratio = ImageStat.Stat(diff).mean[0] / 255.0
            self._audit("verify", f"change_ratio={ratio:.4f}", method="pixels", target=str(before_path), result=f"{ratio:.4f}")
            return {"success": True, "changed_ratio": ratio, "after": after_path}
        except Exception as e:
            logger.warning(f"pixel_change failed: {e}")
            return self._err(str(e))
