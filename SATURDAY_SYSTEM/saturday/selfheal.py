"""SATURDAY Self-Heal — the watchdog that fixes SATURDAY itself.

Every 60s it checks the vitals and REPAIRS what it can:
  camera    : service thread dead → restart (cooldown, max 3, then report).
  dashboard : HUD port silent → rebind/restart server.
  ollama    : unreachable → report only (can't install a model for you).
  disk      : < 1GB free → warn loudly (can't free it for you).
  memory    : < 500MB avail → warn + suggest.
  vault     : locked → report (needs YOUR passphrase — never self-unlocks).
  tasks     : > 3 runaway background agents → warn.

run_checks() is synchronous (the `heal` command + tests use it).
start()/stop() run the background loop. Bounded, quiet, honest.
"""

import logging
import shutil
import threading
import time
from typing import Any, Callable, Dict, List

logger = logging.getLogger("SATURDAY.SelfHeal")

CHECK_INTERVAL = 60.0
RESTART_COOLDOWN = 300.0
MAX_RESTARTS = 3


def free_disk_gb(path: str = "C:\\") -> float:
    try:
        return round(shutil.disk_usage(path).free / (1024 ** 3), 2)
    except Exception:
        return -1.0


def free_mem_mb() -> float:
    try:
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        ms = _MS()
        ms.dwLength = ctypes.sizeof(_MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        return round(ms.ullAvailPhys / (1024 ** 2), 1)
    except Exception:
        return -1.0


class SelfHeal:
    def __init__(self, core, session):
        self.core = core
        self.session = session
        self.last: List[Dict[str, Any]] = []
        self.restarts: Dict[str, int] = {}
        self._cooldowns: Dict[str, float] = {}
        self._stop = threading.Event()
        self._thread = None

    def _may_restart(self, key: str) -> bool:
        now = time.time()
        if self.restarts.get(key, 0) >= MAX_RESTARTS:
            return False
        if now - self._cooldowns.get(key, 0) < RESTART_COOLDOWN:
            return False
        self._cooldowns[key] = now
        self.restarts[key] = self.restarts.get(key, 0) + 1
        return True

    def _ok(self, name: str, detail: str = "", healed: bool = False):
        return {"name": name, "ok": True, "detail": detail, "healed": healed}

    def _bad(self, name: str, detail: str):
        return {"name": name, "ok": False, "detail": detail, "healed": False}

    def run_checks(self) -> List[Dict[str, Any]]:
        out = []
        # Camera: restart the service thread if it died.
        try:
            cam = self.session.camera
            if cam.running:
                out.append(self._ok("camera", f"{cam.frames_captured} frames"))
            elif self._may_restart("camera"):
                cam.start()
                out.append(self._ok("camera", "service restarted", healed=True))
            else:
                out.append(self._bad("camera", f"giving up: {cam.last_error or 'no camera'}"))
        except Exception as e:
            out.append(self._bad("camera", str(e)[:100]))
        # Dashboard: re-ping, restart server object if silent.
        # Token-aware: a shared dashboard 403s strangers but answers its token.
        try:
            dash = self.core._dashboard
            alive = False
            if dash and dash.running:
                import urllib.request
                headers = {}
                if getattr(dash, "shared", False) and getattr(dash, "token", ""):
                    headers["X-Saturday-Token"] = dash.token
                req = urllib.request.Request(dash.url() + "api/status", headers=headers)
                with urllib.request.urlopen(req, timeout=4) as r:
                    alive = r.status == 200
            if alive:
                out.append(self._ok("dashboard", dash.url()))
            elif dash and self._may_restart("dashboard"):
                dash.stop()
                res = dash.start()
                out.append(self._ok("dashboard", "rebound" if res.get("success") else "restart failed",
                                    healed=res.get("success", False)))
            else:
                out.append(self._bad("dashboard", "HUD silent"))
        except Exception as e:
            out.append(self._bad("dashboard", str(e)[:100]))
        # Ollama: report only.
        try:
            from saturday.brain import OllamaBrain

            on = OllamaBrain().available()
            out.append(self._ok("ollama", "llama3.2 reachable") if on
                       else self._bad("ollama", "down (brain falls back to supervised)"))
        except Exception as e:
            out.append(self._bad("ollama", str(e)[:100]))
        # Resources: report only.
        disk = free_disk_gb()
        out.append(self._ok("disk", f"{disk}GB free") if disk > 1
                   else self._bad("disk", f"only {disk}GB free — clean up"))
        mem = free_mem_mb()
        if mem < 0:
            out.append(self._bad("memory", "unreadable"))
        elif mem > 500:
            out.append(self._ok("memory", f"{mem}MB avail"))
        else:
            out.append(self._bad("memory", f"only {mem}MB avail — close heavy apps"))
        # Vault: never self-unlocks; just reports.
        try:
            mounted = bool(self.core.pmv.vault_mounted)
            out.append(self._ok("vault", "mounted") if mounted
                       else self._bad("vault", "locked (needs your passphrase)"))
        except Exception as e:
            out.append(self._bad("vault", str(e)[:100]))
        # Runaway background agents.
        try:
            n = sum(1 for t in threading.enumerate() if (t.name or "").startswith("task-"))
            out.append(self._ok("agents", f"{n} background") if n <= 3
                       else self._bad("agents", f"{n} runaway background agents"))
        except Exception as e:
            out.append(self._bad("agents", str(e)[:100]))
        self.last = out
        return out

    def summary(self) -> str:
        if not self.last:
            return "🩺 Healer has not run yet. Use: heal"
        lines = []
        for c in self.last:
            mark = "✅" if c["ok"] else "❌"
            heal = " (self-healed)" if c.get("healed") else ""
            lines.append(f"   {mark} {c['name']}: {c.get('detail', '')}{heal}")
        return "🩺 Self-heal status:\n" + "\n".join(lines)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="selfheal")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        self._thread = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                bad = [c for c in self.run_checks() if not c["ok"]]
                if bad:
                    logger.warning(f"Self-heal: {len(bad)} issue(s): "
                                   + ", ".join(c["name"] for c in bad))
            except Exception as e:
                logger.debug(f"Self-heal loop failed: {e}")
            self._stop.wait(CHECK_INTERVAL)
