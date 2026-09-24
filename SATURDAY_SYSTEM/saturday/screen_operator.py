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
import tempfile
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Screen")

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

    # -- internals -----------------------------------------------------
    def _err(self, reason: str) -> Dict[str, Any]:
        return {"success": False, "error": reason}

    def _need_backend(self) -> Optional[Dict[str, Any]]:
        if not _PYAUTOGUI_AVAILABLE:
            return self._err(f"pyautogui unavailable ({_IMPORT_ERROR}); pip install pyautogui")
        return None

    def _audit(self, action: str, detail: str) -> None:
        entry = {"action": action, "detail": detail, "at": time.time()}
        self.history.append(entry)
        self.history = self.history[-200:]  # bounded: safe for months of use
        logger.info(f"Screen action: {action} ({detail})")

    def _gated(self, action: str, confirm: bool) -> Optional[Dict[str, Any]]:
        if not confirm:
            return self._err(
                f"'{action}' requires explicit confirmation (confirm=True). "
                "Refusing: remote/untrusted callers may not drive the screen."
            )
        return None

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
                path = str(Path(tempfile.gettempdir()) / f"saturday_see_{int(time.time())}.png")
            shot = pyautogui.screenshot()
            shot.save(path)
            w, h = shot.size
            self._audit("screenshot", f"{path} [{w}x{h}]")
            return {"success": True, "path": path, "width": w, "height": h}
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
            self._audit("open_url", target)
            return {"success": True, "url": target}
        except Exception as e:
            logger.warning(f"open_url failed: {e}")
            return self._err(str(e))

    def open_app(self, app_name: str, confirm: bool = False) -> Dict[str, Any]:
        gated = self._gated("open_app", confirm)
        if gated:
            return gated
        missing = self._need_backend()
        if missing:
            return missing
        app_name = (app_name or "").strip()
        if not app_name:
            return self._err("Empty app name.")
        if len(app_name) > 120:
            return self._err("App name too long.")
        try:
            pyautogui.press("win")
            time.sleep(0.5)
            pyautogui.write(app_name, interval=0.05)
            time.sleep(0.5)
            pyautogui.press("enter")
            self._audit("open_app", app_name)
            return {"success": True, "app": app_name}
        except Exception as e:
            logger.warning(f"open_app failed: {e}")
            return self._err(str(e))

    def click(self, x: int, y: int, confirm: bool = False) -> Dict[str, Any]:
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
        try:
            pyautogui.click(x, y)
            self._audit("click", f"({x},{y})")
            return {"success": True, "x": x, "y": y}
        except Exception as e:
            logger.warning(f"click failed: {e}")
            return self._err(str(e))

    def type_text(self, text: str, confirm: bool = False, interval: float = 0.02) -> Dict[str, Any]:
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
        try:
            pyautogui.write(text, interval=interval)
            # Deliberately log/store length only — never the content.
            self._audit("type", f"{len(text)} chars")
            return {"success": True, "chars": len(text)}
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
            self._audit("press", key)
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
            self._audit("hotkey", "+".join(keys))
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
            self._audit("scroll", str(amount))
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
            self._audit("read", f"{len(words)} words from {path}")
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
            self._audit("verify", f"change_ratio={ratio:.4f}")
            return {"success": True, "changed_ratio": ratio, "after": after_path}
        except Exception as e:
            logger.warning(f"pixel_change failed: {e}")
            return self._err(str(e))
