"""SATURDAY Share — free online server via Cloudflare quick tunnel.

No account, no card, no payment: `cloudflared tunnel --url` exposes the
local HUD on a public https://*.trycloudflare.com URL. Outbound-only
tunnel (nothing listens on your network), dashboard token auth enforced.

URLs are temporary (rotate on restart) — perfect for phone access and
demos. For a permanent address, point a domain at a named tunnel
(cloudflared login) or put SATURDAY on an Oracle free-tier VM (see README).

NEVER share without the dashboard token: the token is generated on
`share on` and shown ONCE. Anyone with URL+token drives SATURDAY.
"""

import logging
import os
import re
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("SATURDAY.Share")

URL_RE = re.compile(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com")
_EXTRA_PATHS = [r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
                r"C:\Program Files\cloudflared\cloudflared.exe"]


def find_cloudflared() -> str:
    hit = shutil.which("cloudflared")
    if hit:
        return hit
    for p in _EXTRA_PATHS:
        if os.path.exists(p):
            return p
    return ""


class ShareLink:
    """One tunnel lifetime. start() blocks ≤60s hunting the public URL."""

    def __init__(self, binary: str = ""):
        self.binary = binary or find_cloudflared()
        self.proc = None
        self.url = ""
        self.port = 0
        self._reader = None
        self._lines: list = []

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, port: int, timeout: float = 60.0, hostname: str = "") -> Dict[str, Any]:
        """Quick tunnel (rotating URL) or --hostname stable endpoint (free account)."""
        if self.running:
            return {"success": True, "url": self.url, "note": "already shared"}
        if not self.binary:
            return {"success": False, "error": (
                "cloudflared missing. Install: winget install Cloudflare.cloudflared")}
        self.stop()
        cmd = [self.binary, "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"]
        if hostname:
            cmd += ["--hostname", hostname]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, bufsize=1)
        except Exception as e:
            return {"success": False, "error": f"cloudflared launch failed: {e}"}
        self.port = port
        deadline = time.time() + timeout
        try:
            while time.time() < deadline and self.running and not self.url:
                line = self.proc.stdout.readline() if self.proc.stdout else ""
                if not line:
                    time.sleep(0.3)
                    continue
                self._lines.append(line)
                self._lines = self._lines[-50:]
                m = URL_RE.search(line)
                if m:
                    self.url = m.group(0)
                elif hostname and hostname in line and ("https://" in line or "Registered" in line):
                    self.url = f"https://{hostname}"
            if not self.url:
                # Hostname tunnels print little: alive process + port = success.
                if hostname and self.running:
                    self.url = f"https://{hostname}"
                else:
                    self.stop()
                    tail = " ".join(self._lines[-5:])
                    return {"success": False,
                            "error": f"No tunnel URL in {timeout:g}s. cloudflared says: {tail[:300]}"}
            logger.warning(f"Internet share LIVE at {self.url} — guard the token.")
            return {"success": True, "url": self.url}
        except Exception as e:
            self.stop()
            return {"success": False, "error": str(e)[:200]}

    def status(self) -> Dict[str, Any]:
        return {"running": self.running, "url": self.url, "port": self.port,
                "binary": bool(self.binary)}

    def stop(self):
        if self._reader:
            try:
                self._reader.join(timeout=2.0)
            except Exception:
                pass
            self._reader = None
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=8.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
        if self.url:
            logger.info("Internet share closed.")
        self.url = ""
