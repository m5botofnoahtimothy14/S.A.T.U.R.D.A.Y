"""
RemoteDesktopManager
--------------------
Launches the native Remote Desktop client to a given host on request.
Listens for "remote_connect" events and voice commands mentioning "remote" or "desktop".
"""
import subprocess
import logging
import re
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.RemoteDesktop")


class RemoteDesktopManager:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.event_bus.subscribe("remote_connect", self._on_remote_connect)
        self.event_bus.subscribe("voice_command", self._on_voice_command)

    def _on_voice_command(self, text: str):
        if not text:
            return
        lower = text.lower()
        if "remote" in lower or "desktop" in lower:
            host = self._extract_host(lower)
            if host:
                self.connect(host)
                self.event_bus.publish("voice_response", f"Opening remote desktop to {host}.")
            else:
                self.event_bus.publish("voice_response", "Say 'remote to hostname or IP' to connect.")

    def _extract_host(self, text: str):
        # Look for IP-like patterns or words after "to"
        m = re.search(r"remote .*? to ([\\w\\.\\-]+)", text)
        if m:
            return m.group(1)
        m = re.search(r"(\\d+\\.\\d+\\.\\d+\\.\\d+)", text)
        if m:
            return m.group(1)
        return None

    def _on_remote_connect(self, payload):
        host = None
        if isinstance(payload, dict):
            host = payload.get("host")
        elif isinstance(payload, str):
            host = payload
        if host:
            self.connect(host)

    def connect(self, host: str):
        try:
            subprocess.Popen(["mstsc.exe", "/v", host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"Remote Desktop launched to {host}")
        except Exception as e:
            logger.error(f"Failed to launch remote desktop: {e}")
            self.event_bus.publish("voice_response", f"Remote desktop failed: {e}")
