"""SATURDAY Tray — silent boot, then disappear into the system tray.

Boot feels like opening an app, not a terminal:
  pythonw Saturday.pyw   → passphrase dialog → core boots headless →
  browser opens the Control Center → tray icon only. No CMD window, ever.

Tray menu (right-click): Open Control Center · Status · Glow on/off ·
Share on/off · Unlock/Lock vault · Quit. Left-click opens the HUD.
Logs go to logs/saturday.log (RotatingFileHandler in main), never stdout —
pythonw has no console and print() would raise.
"""

import logging
import sys
import threading
import webbrowser
from pathlib import Path

logger = logging.getLogger("SATURDAY.Tray")

PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_state = {"core": None, "icon": None, "hud_url": "http://127.0.0.1:8099", "ready": False}


def _log(*a):
    try:
        logger.info(" ".join(str(x) for x in a))
    except Exception:
        pass


def _draw_icon(active=True):
    from PIL import Image, ImageDraw

    size = 64
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ring = (0, 242, 254, 255) if active else (100, 116, 139, 255)
    d.ellipse([6, 6, size - 6, size - 6], outline=ring, width=5)
    d.ellipse([20, 20, size - 20, size - 20], outline=ring, width=3)
    d.ellipse([29, 29, size - 29, size - 29], fill=ring)
    return im


def _ask_passphrase():
    """One GUI prompt (tkinter dialog works under pythonw, no console)."""
    try:
        import tkinter as tk
        from tkinter import simpledialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        pw = simpledialog.askstring("SATURDAY", "Vault passphrase:",
                                    show="*", parent=root)
        try:
            root.destroy()
        except Exception:
            pass
        return pw or ""
    except Exception as e:
        _log(f"passphrase dialog unavailable: {e}")
        return ""


def _boot(icon=None):
    """Runs in pystray setup thread: full core boot, then browser + ready."""
    import pystray  # noqa  (already imported by caller; keeps flake quiet)
    _log("tray boot starting (silent, no console)")
    try:
        from saturday.saturday_core import SATURDAYCore
    except Exception as e:
        _log(f"core import failed: {e}")
        return
    pw = _ask_passphrase()
    if not pw or len(pw) < 8:
        _log("boot aborted: no passphrase")
        try:
            if icon is not None:
                icon.notify("SATURDAY boot aborted — no passphrase.", "SATURDAY")
                icon.stop()
        except Exception:
            pass
        return
    try:
        core = SATURDAYCore(passphrase=pw, project_root=PROJECT_ROOT)
        core.initialize()
        _state["core"] = core
        _log("core online")
    except Exception as e:
        _log(f"core boot failed: {e}")
        try:
            if icon is not None:
                icon.notify(f"Boot failed: {e}", "SATURDAY")
        except Exception:
            pass
        return
    # HUD URL (dashboard auto-started by session on 8099)
    try:
        url = getattr(getattr(core, "session", None), "dashboard_url", "") or _state["hud_url"]
        if url:
            _state["hud_url"] = url
    except Exception:
        pass
    _state["ready"] = True
    try:
        if icon is not None:
            icon.icon = _draw_icon(active=True)
            icon.notify("SATURDAY online — Control Center opening.", "SATURDAY")
    except Exception:
        pass
    try:
        webbrowser.open(_state["hud_url"])
        _log(f"browser opened: {_state['hud_url']}")
    except Exception as e:
        _log(f"browser open failed: {e}")


def _cmd(text):
    core = _state.get("core")
    if core is None or not _state.get("ready"):
        return "booting…"
    try:
        return core.process_command(text, trusted=True)
    except Exception as e:
        return f"❌ {e}"


def _menu():
    import pystray

    def _open(icon, item):
        webbrowser.open(_state["hud_url"])

    def _status(icon, item):
        out = _cmd("status")
        try:
            icon.notify(out[:220], "SATURDAY status")
        except Exception:
            pass

    def _glow_on(icon, item):
        _cmd("glow on")

    def _glow_off(icon, item):
        _cmd("glow off")

    def _share(icon, item):
        out = _cmd("share on")
        try:
            icon.notify(out[:220], "SATURDAY share")
        except Exception:
            pass

    def _quit(icon, item):
        _log("tray quit requested")
        core = _state.get("core")
        try:
            if core is not None:
                core.shutdown()
        except Exception:
            pass
        icon.stop()

    return pystray.Menu(
        pystray.MenuItem("Open Control Center", _open, default=True),
        pystray.MenuItem("Status", _status),
        pystray.MenuItem("Glow on", _glow_on),
        pystray.MenuItem("Glow off", _glow_off),
        pystray.MenuItem("Share on (phone link)", _share),
        pystray.MenuItem("Quit SATURDAY", _quit),
    )


def run():
    """Main-thread entry: icon.run() blocks here until Quit."""
    import pystray

    icon = pystray.Icon("SATURDAY", _draw_icon(active=False),
                        "SATURDAY (starting…)", _menu())
    _state["icon"] = icon

    def _setup(ic):
        ic.visible = True
        threading.Thread(target=_boot, args=(ic,), daemon=True,
                         name="tray-boot").start()

    icon.run(setup=_setup)


if __name__ == "__main__":
    from main import initialize_logging
    initialize_logging("INFO")
    run()
