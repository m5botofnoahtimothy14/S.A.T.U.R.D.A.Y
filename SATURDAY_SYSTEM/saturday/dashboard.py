"""SATURDAY Dashboard — local high-tech HUD. Stdlib only, offline forever.

ThreadingHTTPServer bound to 127.0.0.1 (this PC only — never exposed).
Routes:
  GET  /                  → HUD (dashboard/index.html)
  GET  /api/status        → core status + homebot + uptime + subsystem flags
  POST /api/command       → {"command": "..."} → core.process_command (local trust)
  GET  /api/tasks         → recent autonomous task summaries
  GET  /api/homebot       → Core2 link status + telemetry
  POST /api/homebot       → {"command","duration","speed"} → drive the bot
  GET  /api/log           → recent server-side events (bounded)

Long-run design: daemon threads, bounded buffers everywhere, per-request
try/except so one bad call never kills the server, JSON errors (never
tracebacks) to the browser with auto-reconnect polling.
"""

import json
import logging
import threading
import time
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("SATURDAY.Dashboard")

import os as _os
import sys as _sys


def _cors_origin(handler) -> str:
    """Value for Access-Control-Allow-Origin, or '' if CORS disabled."""
    allowed = [o.strip() for o in _os.getenv("SATURDAY_CORS_ORIGIN", "").split(",") if o.strip()]
    if not allowed:
        return ""
    req = handler.headers.get("Origin", "")
    if "*" in allowed:
        return "*"
    if req and req in allowed:
        return req
    return ""


def _app_dir() -> Path:
    if getattr(_sys, "frozen", False):
        # PyInstaller 6 one-dir: bundled resources live in _internal/.
        meipass = getattr(_sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(_sys.executable).resolve().parent
    return Path(__file__).parent.parent


DASH_DIR = _app_dir() / "dashboard"
MAX_BODY = 32 * 1024
MAX_EVENTS = 200


class DashboardServer:
    def __init__(self, core, homebot_link=None, host: str = "127.0.0.1", port: int = 8099):
        self.core = core
        self.homebot_link = homebot_link
        self.host = host
        self.port = port
        self.started_at = time.time()
        self.events: list = []
        self.shared = False
        self.token = ""
        self._server = None
        self._thread = None

    def share(self, token: str = "") -> Dict[str, Any]:
        """Internet-share mode: ALL routes require the token. Returns it (show once).

        Idempotent: sharing twice without a new token KEEPS the current one
        (prevents concurrent callers from desyncing URL files vs memory).
        Pass an explicit token (or unshare first) to rotate."""
        import secrets as _secrets

        if self.shared and self.token and not token:
            return {"success": True, "token": self.token, "note": "already shared"}
        if not token:
            token = _secrets.token_urlsafe(24)
        self.token = token
        self.shared = True
        self.note("server", "Internet share ON — token required on all routes.")
        logger.warning("Dashboard shared to the internet — token auth enforced.")
        return {"success": True, "token": token}

    def unshare(self) -> Dict[str, Any]:
        self.shared = False
        self.token = ""
        self.note("server", "Internet share OFF.")
        return {"success": True}

    def _authorized(self, handler) -> bool:
        if not self.shared:
            return True
        if handler.headers.get("X-Saturday-Token", "") == self.token and self.token:
            return True
        import urllib.parse as _up
        q = _up.urlparse(handler.path).query
        params = _up.parse_qs(q)
        return bool(self.token) and params.get("token", [""])[0] == self.token

    def note(self, kind: str, message: str):
        self.events.append({"ts": time.time(), "kind": kind, "message": str(message)[:300]})
        self.events = self.events[-MAX_EVENTS:]

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> Dict[str, Any]:
        if self.running:
            return {"success": True, "url": self.url(), "note": "already running"}
        try:
            handler = partial(_Handler, server_ref=self)
            self._server = ThreadingHTTPServer((self.host, self.port), handler)
            self.port = self._server.server_address[1]  # real port if 0 given
            self._thread = threading.Thread(target=self._server.serve_forever,
                                            kwargs={"poll_interval": 0.5},
                                            daemon=True, name="dashboard-http")
            self._thread.start()
            self.note("server", f"Hud up at {self.url()}")
            logger.info(f"Dashboard HUD up at {self.url()}")
            return {"success": True, "url": self.url()}
        except Exception as e:
            logger.warning(f"Dashboard start failed: {e}")
            return {"success": False, "error": str(e)}

    def stop(self):
        try:
            if self._server:
                self._server.shutdown()
                self._server.server_close()
        except Exception:
            pass
        self._thread = None

    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def status_payload(self) -> Dict[str, Any]:
        try:
            base = self.core.get_status_payload()
        except Exception as e:
            base = {"online": False, "error": str(e)}
        bot = None
        try:
            if self.homebot_link:
                bot = self.homebot_link.status()
        except Exception as e:
            bot = {"error": str(e)}
        base["homebot"] = bot
        base["dashboard_uptime_s"] = round(time.time() - self.started_at, 1)
        base["server_time"] = time.time()
        return base


def _frame_payload(ref: DashboardServer) -> Dict[str, Any]:
    """Latest session camera frame as JPEG base64 (localhost HUD only)."""
    try:
        session = getattr(ref.core, "session", None)
        frame = session.camera.get_frame(max_age=5.0) if session else None
        if frame is None:
            return {"available": False}
        from PIL import Image
        import base64 as _b64
        import io as _io
        rgb = frame[:, :, ::-1]
        img = Image.fromarray(rgb).resize((320, 180))
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=55)
        return {"available": True,
                "image": _b64.b64encode(buf.getvalue()).decode(),
                "age_s": round(session.camera.age or 0, 1)}
    except Exception as e:
        return {"available": False, "error": str(e)[:120]}


def _mic_payload(ref: DashboardServer) -> Dict[str, Any]:
    """Live mic activity for the HUD meter (clap-listener stream levels)."""
    try:
        session = getattr(ref.core, "session", None)
        claps = getattr(session, "claps", None) if session else None
        if claps is None:
            return {"live": False, "reason": "clap listener not running"}
        st = claps.status()
        return {"live": bool(st.get("live")), "floor": st.get("noise_floor", 0),
                "peak": st.get("peak", 0), "peak_age_s": st.get("peak_age_s", 0),
                "singles": st.get("singles", 0), "doubles": st.get("doubles", 0)}
    except Exception as e:
        return {"live": False, "error": str(e)[:120]}


class _Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, server_ref: DashboardServer = None, **kwargs):
        self.server_ref = server_ref
        super().__init__(*args, **kwargs)

    def log_message(self, *args):
        pass  # keep console clean; events API carries what matters

    def _send(self, code: int, obj=None, content_type="application/json"):
        try:
            body = json.dumps(obj).encode() if obj is not None else b""
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            origin = _cors_origin(self)
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def do_OPTIONS(self):
        try:
            origin = _cors_origin(self)
            self.send_response(204)
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Saturday-Token")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Vary", "Origin")
            self.send_header("Content-Length", "0")
            self.end_headers()
        except Exception:
            pass

    def _send_file(self, path: Path, content_type: str):
        try:
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self._send(404, {"error": "not found"})

    def do_GET(self):
        ref = self.server_ref
        try:
            if not ref._authorized(self):
                return self._send(403, {"error": "token required (?token= or X-Saturday-Token)"})
            import urllib.parse as _up
            route = _up.urlparse(self.path).path
            if route in ("/", "/index.html"):
                return self._send_file(DASH_DIR / "index.html", "text/html; charset=utf-8")
            if route == "/api/status":
                return self._send(200, ref.status_payload())
            if route == "/api/tasks":
                items = [t.summary() for t in getattr(ref.core, "agent_history", [])[-20:]]
                inbox = []
                try:
                    session = getattr(ref.core, "session", None)
                    if session is not None:
                        inbox = [{"id": i["id"], "status": i["status"],
                                  "priority": i["priority"],
                                  "text": (i.get("goal") or i.get("text") or "")[:90]}
                                 for i in session.inbox_list()]
                except Exception:
                    pass
                return self._send(200, {"tasks": items, "inbox": inbox})
            if route == "/api/homebot":
                if ref.homebot_link:
                    return self._send(200, ref.homebot_link.status())
                return self._send(200, {"error": "homebot link not started"})
            if route == "/api/log":
                return self._send(200, {"events": ref.events[-50:]})
            if route == "/api/frame":
                return self._send(200, _frame_payload(ref))
            if route == "/api/miclevel":
                return self._send(200, _mic_payload(ref))
            return self._send(404, {"error": "unknown route"})
        except Exception as e:
            ref.note("error", f"GET {self.path}: {e}")
            return self._send(500, {"error": str(e)[:200]})

    def do_POST(self):
        ref = self.server_ref
        try:
            if not ref._authorized(self):
                return self._send(403, {"error": "token required (X-Saturday-Token)"})
            import urllib.parse as _up2
            route = _up2.urlparse(self.path).path
            length = min(int(self.headers.get("Content-Length", 0) or 0), MAX_BODY)
            raw = self.rfile.read(length) if length else b""
            try:
                data = json.loads(raw.decode() or "{}")
            except Exception:
                return self._send(400, {"error": "invalid JSON"})
            if route == "/api/command":
                cmd = str(data.get("command", "")).strip()
                if not cmd:
                    return self._send(400, {"error": "empty command"})
                if len(cmd) > 2000:
                    return self._send(400, {"error": "command too long"})
                try:
                    out = ref.core.process_command(cmd, trusted=True)
                except Exception as e:
                    out = f"❌ System Error: {e}"
                ref.note("cmd", cmd[:120])
                return self._send(200, {"response": out})
            if route == "/api/homebot":
                if not ref.homebot_link:
                    return self._send(200, {"status": "unavailable",
                                            "reason": "homebot link not started"})
                name = str(data.get("command", ""))
                res = ref.homebot_link.command(name,
                                               duration=float(data.get("duration", 1.0) or 0),
                                               speed=int(data.get("speed", 80) or 80))
                ref.note("bot", f"{name} → {res.get('status')}")
                return self._send(200, res)
            return self._send(404, {"error": "unknown route"})
        except Exception as e:
            ref.note("error", f"POST {self.path}: {e}")
            return self._send(500, {"error": str(e)[:200]})
