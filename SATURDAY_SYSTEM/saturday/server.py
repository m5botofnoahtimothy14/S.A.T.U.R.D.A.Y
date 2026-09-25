"""SATURDAY Always-On Server — the global layer, separate from the humanoid.

The humanoid (brain, voice, hands, mind) LIVES on this machine. The server
is how it reaches the world and how the world reaches it:

  tunnel   : Cloudflare public URL (persist watchdog, token auth).
  presence : RTDB heartbeat /saturday_presence/<node> = {online, ts, url}
             so ANY device can see "SATURDAY is awake" without the tunnel.
  commands : RTDB inbox /saturday_system/<node>/commands — the realtime
             bridge already executes these as UNTRUSTED (no screen-driving).

One start() brings it all up; status() tells the truth about each leg.
Nothing here holds the vault passphrase or decides anything — that is
the humanoid's job. This module only carries bytes.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("SATURDAY.Server")

HEARTBEAT_EVERY = 60.0


class AlwaysOnServer:
    def __init__(self, core, session):
        self.core = core
        self.session = session
        self.bridge = None
        self.heartbeat_at = 0.0
        self._stop = threading.Event()
        self._thread = None

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        self._stop.clear()
        # Tunnel first (phone path), bridge second (Firebase path).
        try:
            if getattr(self.session, "share_persist", False):
                self.session.ensure_shared()
        except Exception as e:
            logger.debug(f"Server tunnel ensure failed: {e}")
        try:
            self._start_bridge()
        except Exception as e:
            logger.debug(f"Server bridge failed: {e}")
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, daemon=True,
                                            name="alwayson-server")
            self._thread.start()
        logger.info("Always-on server up.")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        self._thread = None
        try:
            if self.bridge:
                self.bridge.stop()
        except Exception:
            pass
        self.bridge = None

    def _start_bridge(self):
        import os as _os
        from realtime_bridge import RealtimeDatabaseBridge

        cfg = getattr(self.core, "cloud_config", {}) or {}
        sa = cfg.get("service_account") or _os.getenv("FIREBASE_SERVICE_ACCOUNT", "")
        url = cfg.get("database_url") or _os.getenv("FIREBASE_DATABASE_URL", "")
        node = cfg.get("node") or _os.getenv("FIREBASE_NODE_ID", "saturday-node")
        if not sa or not url:
            logger.info("Server: no Firebase creds — RTDB legs offline (tunnel only).")
            return
        self.bridge = RealtimeDatabaseBridge(service_account=sa, database_url=url,
                                             node_id=node)
        # Untrusted remote commands: status yes, screen-driving never.
        self.bridge.start(lambda: self.core.get_status_payload(),
                          lambda cmd, meta: self.core.process_command(cmd, trusted=False))
        logger.info("Server: RTDB presence + command inbox live.")

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._heartbeat()
            except Exception as e:
                logger.debug(f"Server heartbeat failed: {e}")
            self._stop.wait(HEARTBEAT_EVERY)

    def _heartbeat(self):
        if not self.bridge or not getattr(self.bridge, "status_ref", None):
            return
        try:
            link = self.core._share_link()
            url = link.url if link and link.running else ""
            self.bridge.status_ref.child("presence").set({
                "online": True, "ts": time.time(), "tunnel_url": url,
                "version": self.core.pmv.settings.get("version", "?"),
            })
            self.heartbeat_at = time.time()
        except Exception as e:
            logger.debug(f"presence heartbeat failed: {e}")

    # -- truth ---------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        try:
            link = self.core._share_link()
            tunnel = {"running": link.running, "url": link.url}
        except Exception:
            tunnel = {"running": False, "url": ""}
        bridge_on = bool(self.bridge and getattr(self.bridge, "running", False))
        return {
            "tunnel": tunnel,
            "persist": bool(getattr(self.session, "share_persist", False)),
            "rtdb": bridge_on,
            "last_heartbeat_s_ago": (round(time.time() - self.heartbeat_at, 1)
                                     if self.heartbeat_at else None),
        }
