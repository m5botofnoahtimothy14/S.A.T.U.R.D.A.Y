"""Tests for the always-on server layer (tunnel + RTDB, no AI)."""
import sys
import time
from pathlib import Path
from unittest import TestCase, main as test_main
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from saturday.server import AlwaysOnServer


def session_mock(**kw):
    m = MagicMock()
    m.share_persist = kw.get("persist", False)
    m.ensure_shared.return_value = {"success": True, "url": "https://u", "token": "T"}
    return m


class TestServer(TestCase):
    def test_starts_quiet_without_creds(self):
        core = MagicMock()
        core.cloud_config = {}
        core.pmv.settings = {"version": "t"}
        core._share_link.return_value.running = False
        core._share_link.return_value.url = ""
        srv = AlwaysOnServer(core, session_mock())
        srv.start()
        try:
            st = srv.status()
            self.assertFalse(st["tunnel"]["running"])
            self.assertFalse(st["rtdb"])
            self.assertIsNone(st["last_heartbeat_s_ago"])
        finally:
            srv.stop()
        print("DONE: server quiet test passed.")

    def test_bridge_untrusted_commands(self):
        core = MagicMock()
        core.cloud_config = {"service_account": "sa.json",
                             "database_url": "https://x", "node": "n"}
        core.pmv.settings = {"version": "t"}
        calls = {}

        class FakeBridge:
            def __init__(self, **kw):
                calls["init"] = kw

            def start(self, status_fn, cmd_fn):
                calls["cmd_fn"] = cmd_fn
                self.running = True

            def stop(self):
                self.running = False

        with patch("realtime_bridge.RealtimeDatabaseBridge", FakeBridge):
            srv = AlwaysOnServer(core, session_mock())
            srv.start()
            try:
                self.assertTrue(srv.status()["rtdb"])
                calls["cmd_fn"]("status", {})
                _, kwargs = core.process_command.call_args
                self.assertEqual(kwargs.get("trusted"), False)
            finally:
                srv.stop()
        print("DONE: bridge untrusted test passed.")

    def test_heartbeat_writes_presence(self):
        core = MagicMock()
        core.cloud_config = {}
        core.pmv.settings = {"version": "9"}
        link = MagicMock()
        link.running = True
        link.url = "https://u"
        core._share_link.return_value = link
        srv = AlwaysOnServer(core, session_mock())
        srv.bridge = MagicMock()
        srv.bridge.status_ref = MagicMock()
        srv._heartbeat()
        args, _ = srv.bridge.status_ref.child.call_args
        self.assertEqual(args[0], "presence")
        payload = srv.bridge.status_ref.child.return_value.set.call_args[0][0]
        self.assertTrue(payload["online"])
        self.assertEqual(payload["tunnel_url"], "https://u")
        self.assertGreater(srv.heartbeat_at, 0)
        print("DONE: heartbeat test passed.")

    def test_server_command(self):
        from saturday.saturday_core import SATURDAYCore
        core = SATURDAYCore.__new__(SATURDAYCore)
        core.pmv = MagicMock()
        core.pmv.auto_lock_check.return_value = False
        core._current_trusted = True
        core.session = MagicMock()
        server = MagicMock()
        server.status.return_value = {"tunnel": {"running": True, "url": "https://u"},
                                      "persist": True, "rtdb": True,
                                      "last_heartbeat_s_ago": 12.0}
        core.session.server = server
        core._command_handlers = SATURDAYCore._build_command_handlers(core)
        out = core.process_command("server", trusted=True)
        self.assertIn("Always-on server", out)
        self.assertIn("https://u", out)
        print("DONE: server command test passed.")

    def test_hud_is_control_plane(self):
        html = (PROJECT_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        web = (PROJECT_ROOT / "vercel-web" / "index.html").read_text(encoding="utf-8")
        for doc in (html, web):
            self.assertIn("CONTROL PLANE", doc)
            self.assertIn("MAINTENANCE", doc)
            self.assertIn("serverline", doc)
        print("DONE: HUD control-plane test passed.")


if __name__ == "__main__":
    test_main(verbosity=2)
