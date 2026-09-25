"""Tests for internet share + cloud backup — Firebase faked, no network."""
import base64
import json
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from unittest import TestCase, main as test_main
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from saturday.dashboard import DashboardServer
from saturday import cloud as cloudmod
from saturday.share import ShareLink


def fake_core():
    core = MagicMock()
    core.get_status_payload.return_value = {"online": True}
    core.process_command.side_effect = lambda c, **kw: f"echo:{c}"
    core.agent_history = []
    return core


def req(port, path, token=None, post=None):
    url = f"http://127.0.0.1:{port}{path}"
    headers = {}
    if token == "header":
        headers["X-Saturday-Token"] = TOK[0]
    data = json.dumps(post).encode() if post is not None else None
    r = urllib.request.Request(url, data=data, headers=headers,
                               method="POST" if post is not None else "GET")
    try:
        with urllib.request.urlopen(r, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


TOK = [""]


class TestShareAuth(TestCase):
    def test_token_gate(self):
        srv = DashboardServer(fake_core(), port=0)
        srv.start()
        try:
            port = srv.port
            code, _ = req(port, "/api/status")
            self.assertEqual(code, 200)  # open on localhost
            tok = srv.share()["token"]
            TOK[0] = tok
            self.assertTrue(len(tok) > 20)
            again = srv.share()["token"]
            self.assertEqual(again, tok)  # idempotent: no rotation, no desync
            code, _ = req(port, "/api/status")
            self.assertEqual(code, 403)  # locked now
            code, ok = req(port, f"/api/status?token={tok}")
            self.assertEqual(code, 200)
            self.assertTrue(ok["online"])
            code, _ = req(port, "/api/command", post={"command": "x"})
            self.assertEqual(code, 403)
            code, out = req(port, "/api/command", token="header", post={"command": "hi"})
            self.assertEqual(code, 200)
            self.assertEqual(out["response"], "echo:hi")
            srv.unshare()
            code, _ = req(port, "/api/status")
            self.assertEqual(code, 200)
        finally:
            srv.stop()
        print("DONE: share token-gate test passed.")


class FakeRef:
    def __init__(self, store, path=""):
        self.store, self.path = store, path

    def child(self, name):
        return FakeRef(self.store, f"{self.path}/{name}".strip("/"))

    def _node(self):
        node = self.store
        for part in self.path.split("/"):
            node = node.setdefault(part, {})
        return node

    def set(self, value):
        *head, leaf = self.path.split("/")
        node = self.store
        for part in head:
            node = node.setdefault(part, {})
        node[leaf] = value

    def get(self):
        node = self.store
        for part in self.path.split("/"):
            node = node.get(part, {})
        return node


def fake_cloud(monkey_store):
    fb = MagicMock()
    fb.get_app.side_effect = ValueError("no app")
    fake_db = MagicMock()
    fake_db.reference.side_effect = lambda p: FakeRef(monkey_store, p.strip("/"))
    return fb, MagicMock(), fake_db


class TestCloudBackup(TestCase):
    def _vault(self, tmp, n=2):
        mem = Path(tmp) / "vault" / "memory"
        mem.mkdir(parents=True)
        for i in range(n):
            (mem / f"e{i}.enc").write_bytes(b"ENCRYPTED-BLOB-%d" % i)
        salt = Path(tmp) / "salt.dat"
        salt.write_bytes(b"0123456789abcdef")
        return str(mem), str(salt)

    def test_backup_restore_roundtrip(self):
        import tempfile as _t
        tmp = _t.mkdtemp(prefix="satcloud_")
        mem, salt = self._vault(tmp)
        sa = str(Path(tmp) / "sa.json")
        Path(sa).write_text("{}")
        store = {}
        fb, cred, fdb = fake_cloud(store)
        with patch.object(cloudmod, "firebase_admin", fb), \
             patch.object(cloudmod, "credentials", cred), \
             patch.object(cloudmod, "db", fdb), \
             patch.object(cloudmod, "_FB_AVAILABLE", True):
            res = cloudmod.backup_vault(mem, salt, sa, "https://x", "n1")
            self.assertTrue(res["success"], res)
            self.assertEqual(res["entries"], 2)
            # Ciphertext only: blobs must NOT contain plaintext.
            blob = store["saturday_backups"]["n1"]["entries"]["e0"]["blob"]
            self.assertNotIn("secret", blob)
            self.assertEqual(base64.b64decode(blob), b"ENCRYPTED-BLOB-0")
            # Restore into a fresh dir fills gaps, then skips.
            mem2 = str(Path(tmp) / "vault2" / "memory")
            r1 = cloudmod.restore_vault(mem2, str(Path(tmp) / "s2.dat"), sa, "https://x", "n1")
            self.assertEqual((r1["restored"], r1["skipped"]), (2, 0))
            self.assertTrue((Path(mem2) / "e1.enc").exists())
            self.assertTrue((Path(tmp) / "s2.dat").exists())  # salt restored too
            r2 = cloudmod.restore_vault(mem2, str(Path(tmp) / "s2.dat"), sa, "https://x", "n1")
            self.assertEqual((r2["restored"], r2["skipped"]), (0, 2))
        print("DONE: cloud backup roundtrip test passed.")

    def test_traversal_rejected(self):
        import tempfile as _t
        tmp = _t.mkdtemp(prefix="satcloud2_")
        sa = str(Path(tmp) / "sa.json")
        Path(sa).write_text("{}")
        store = {"saturday_backups": {"n": {"entries": {"../evil": {"blob": base64.b64encode(b"x").decode()}}}}}
        fb, cred, fdb = fake_cloud(store)
        with patch.object(cloudmod, "firebase_admin", fb), \
             patch.object(cloudmod, "credentials", cred), \
             patch.object(cloudmod, "db", fdb), \
             patch.object(cloudmod, "_FB_AVAILABLE", True):
            res = cloudmod.restore_vault(str(Path(tmp) / "m"), str(Path(tmp) / "s"), sa, "https://x", "n")
            self.assertTrue(res["success"])
            self.assertEqual(res["restored"], 0)
            self.assertFalse((Path(tmp) / "evil").exists())
        print("DONE: cloud traversal test passed.")


class TestShareLink(TestCase):
    def test_url_parse_and_stop(self):
        link = ShareLink(binary="cloudflared")
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdout.readline.side_effect = [
            "2026 init...\n",
            "https://random-name-123.trycloudflare.com arrived\n",
        ]
        with patch("subprocess.Popen", return_value=proc), \
             patch.object(ShareLink, "_verify_public", return_value=True):
            res = link.start(8099, timeout=10)
            self.assertTrue(res["success"])
            self.assertIn("trycloudflare.com", res["url"])
            self.assertTrue(link.running)
            link.stop()
            self.assertFalse(link.running)
            proc.terminate.assert_called()
        print("DONE: share link test passed.")

    def test_no_binary(self):
        link = ShareLink(binary="")
        with patch("saturday.share.find_cloudflared", return_value=""):
            link.binary = ""
            res = link.start(8099, timeout=1)
            self.assertFalse(res["success"])
        print("DONE: share no-binary test passed.")


class TestCloudCommands(TestCase):
    def _core(self):
        from saturday.saturday_core import SATURDAYCore
        core = SATURDAYCore.__new__(SATURDAYCore)
        core.pmv = MagicMock()
        core.pmv.auto_lock_check.return_value = False
        core.screen = MagicMock()
        core.agent_history = []
        core._homebot = core._dashboard = core._brain_probe = core.session = None
        core.cmd_counts = {}
        core._gallery_cache = core._voice_cache = None
        core._share_obj = None
        core.cloud_config = {}
        core.is_running = True
        core._command_handlers = SATURDAYCore._build_command_handlers(core)
        return core

    def test_cloudsetup_validation(self):
        core = self._core()
        out = core.process_command("cloudsetup", trusted=True)
        self.assertIn("Usage", out)
        out = core.process_command("cloudsetup /nope.json https://x", trusted=True)
        self.assertIn("not found", out)
        print("DONE: cloudsetup validation test passed.")

    def test_share_status_off(self):
        core = self._core()
        with patch("saturday.share.ShareLink") as SL:
            SL.return_value.status.return_value = {"running": False}
            out = core.process_command("share", trusted=True)
            self.assertIn("Not sharing", out)
        print("DONE: share status test passed.")

    def test_share_persist_arms_watchdog(self):
        core = self._core()
        core.session = MagicMock()
        out = core.process_command("share persist mybot.example.com", trusted=True)
        self.assertIn("Persist ON", out)
        self.assertTrue(core.session.share_persist)
        self.assertEqual(core.session.share_hostname, "mybot.example.com")
        print("DONE: share persist test passed.")

    def test_reap_stale_clean(self):
        from saturday.share import reap_stale
        self.assertGreaterEqual(reap_stale(8099), 0)
        print("DONE: reap stale test passed.")

    def test_share_on_with_hostname(self):
        core = self._core()
        core._dashboard = MagicMock()
        core._dashboard.port = 8099
        core._dashboard.share.return_value = {"token": "T"}
        with patch("saturday.share.ShareLink") as SL:
            SL.return_value.start.return_value = {"success": True, "url": "https://h"}
            out = core.process_command("share on mybot.cfargotunnel.com", trusted=True)
            self.assertIn("ONLINE", out)
            _, kwargs = SL.return_value.start.call_args
            self.assertEqual(kwargs.get("hostname"), "mybot.cfargotunnel.com")
        print("DONE: share hostname test passed.")


class TestCORSAndPersist(TestCase):
    def test_cors_headers(self):
        import os
        srv = DashboardServer(fake_core(), port=0)
        srv.start()
        try:
            port = srv.port
            with patch.dict("os.environ", {"SATURDAY_CORS_ORIGIN": "https://x.vercel.app"}):
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/status",
                    headers={"Origin": "https://x.vercel.app"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    self.assertEqual(r.headers.get("Access-Control-Allow-Origin"),
                                     "https://x.vercel.app")
                evil = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/status",
                    headers={"Origin": "https://evil.test"})
                with urllib.request.urlopen(evil, timeout=5) as r:
                    self.assertIsNone(r.headers.get("Access-Control-Allow-Origin"))
        finally:
            srv.stop()
        print("DONE: CORS test passed.")

    def test_persist_restarts_tunnel(self):
        from saturday.session import SessionManager
        core = MagicMock()
        core._dashboard = MagicMock()
        core._dashboard.running = True
        core._dashboard.port = 8099
        core._dashboard.share.return_value = {"token": "T"}
        link = MagicMock()
        link.running = False
        link.start.return_value = {"success": True, "url": "https://u"}
        core._share_link.return_value = link
        mgr = SessionManager(core)
        mgr.share_persist = True
        res = mgr.ensure_shared()
        self.assertTrue(res["success"])
        self.assertEqual(res["url"], "https://u")
        link.start.assert_called_once()
        print("DONE: persist ensure test passed.")


if __name__ == "__main__":
    test_main(verbosity=2)
