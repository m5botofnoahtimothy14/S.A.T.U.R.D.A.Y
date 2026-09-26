"""Tests for HUD server + HomeBot link + long-run hardening. Real HTTP, mocked hardware."""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from unittest import TestCase, main as test_main
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from saturday.dashboard import DashboardServer
from saturday.homebot import HomeBotLink, CMD_TOPIC


def fake_core():
    core = MagicMock()
    core.get_status_payload.return_value = {"online": True, "version": "t"}
    core.process_command.side_effect = lambda c, **kw: f"echo:{c}"
    core.agent_history = []
    return core


def http_get(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def http_post(port, path, obj):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


class TestDashboard(TestCase):
    def test_full_api_cycle(self):
        srv = DashboardServer(fake_core(), port=0)
        res = srv.start()
        self.assertTrue(res["success"], res)
        self.assertTrue(srv.running)
        try:
            port = srv.port
            code, status = http_get(port, "/api/status")
            self.assertEqual(code, 200)
            self.assertTrue(status["online"])
            code, out = http_post(port, "/api/command", {"command": "status"})
            self.assertEqual(out["response"], "echo:status")
            code, bad = http_post(port, "/api/command", {"command": ""})
            self.assertEqual(code, 400)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
                html = r.read().decode()
                self.assertIn("SATURDAY", html)
                self.assertIn("/api/status", html)
            code, unknown = http_get(port, "/api/nope")
            self.assertEqual(code, 404)
        finally:
            srv.stop()
        print("DONE: dashboard API test passed.")

    def test_command_errors_stay_json(self):
        core = fake_core()
        core.process_command.side_effect = RuntimeError("boom")
        srv = DashboardServer(core, port=0)
        srv.start()
        try:
            code, out = http_post(srv.port, "/api/command", {"command": "x"})
            self.assertEqual(code, 200)
            self.assertIn("System Error", out["response"])
        finally:
            srv.stop()
        print("DONE: dashboard error-envelope test passed.")

    def test_query_routes_and_miclevel(self):
        core = fake_core()
        core.session = None
        srv = DashboardServer(core, port=0)
        srv.start()
        try:
            port = srv.port
            tok = srv.share()["token"]
            # Token-in-query must route, not 404 (phone HUD uses ?token=).
            code, out = http_get(port, f"/api/homebot?token={tok}")
            self.assertEqual(code, 200)
            code, out = http_get(port, f"/api/log?token={tok}")
            self.assertEqual(code, 200)
            code, out = http_get(port, f"/api/miclevel?token={tok}")
            self.assertEqual(code, 200)
            self.assertIn("live", out)
            self.assertFalse(out["live"])  # no session/claps here
        finally:
            srv.stop()
        print("DONE: query-route + miclevel test passed.")


class TestHomeBot(TestCase):
    def test_no_hardware_honest(self):
        link = HomeBotLink(broker="", com_port="", autostart=False)
        res = link.command("forward")
        self.assertEqual(res["status"], "unavailable")
        st = link.status()
        self.assertFalse(st["bot_seen"])
        self.assertEqual(st["transport"], "none")
        self.assertIsInstance(st["ports"], list)
        print("DONE: homebot no-hardware test passed.")

    def test_mqtt_command_and_autostop(self):
        import paho.mqtt.client as mqtt_mod
        link = HomeBotLink(broker="127.0.0.1", autostart=False)
        fake_client = MagicMock()
        fake_info = MagicMock()
        fake_info.rc = mqtt_mod.MQTT_ERR_SUCCESS
        fake_client.publish.return_value = fake_info
        link.client = fake_client
        link.broker_connected = True
        res = link.command("forward", duration=0.1, speed=50)
        self.assertEqual(res["status"], "success")
        topic, payload = fake_client.publish.call_args[0]
        self.assertEqual(topic, CMD_TOPIC)
        body = json.loads(payload)
        self.assertAlmostEqual(body["motion"]["vx"], 0.5)
        time.sleep(0.4)  # auto-STOP timer
        stop_payload = json.loads(fake_client.publish.call_args[0][1])
        self.assertTrue(stop_payload.get("stop"))
        print("DONE: homebot mqtt+autostop test passed.")

    def test_unknown_command(self):
        link = HomeBotLink(broker="", autostart=False)
        res = link.command("dance")
        self.assertEqual(res["status"], "unavailable")
        print("DONE: homebot unknown-cmd test passed.")

    def _mqtt_link(self):
        import paho.mqtt.client as mqtt_mod
        link = HomeBotLink(broker="127.0.0.1", autostart=False)
        fake_client = MagicMock()
        fake_info = MagicMock()
        fake_info.rc = mqtt_mod.MQTT_ERR_SUCCESS
        fake_client.publish.return_value = fake_info
        link.client = fake_client
        link.broker_connected = True
        return link, fake_client

    def test_patrol_moves_and_autostops(self):
        import json as _json
        link, fake_client = self._mqtt_link()
        res = link.patrol(minutes=0.1, speed=50)
        self.assertEqual(res["status"], "success")
        busy = link.patrol(minutes=1)
        self.assertEqual(busy["status"], "unavailable")
        link._patrol_thread.join(timeout=15)
        topics = [c[0][0] for c in fake_client.publish.call_args_list]
        self.assertTrue(all(t == CMD_TOPIC for t in topics))
        last = _json.loads(fake_client.publish.call_args_list[-1][0][1])
        self.assertTrue(last.get("stop"))
        print("DONE: patrol auto-stop test passed.")

    def test_stop_cancels_patrol(self):
        link, _ = self._mqtt_link()
        res = link.patrol(minutes=5, speed=50)
        self.assertEqual(res["status"], "success")
        link.command("stop")
        link._patrol_thread.join(timeout=10)
        self.assertFalse(link._patrol_thread.is_alive())
        print("DONE: patrol cancel test passed.")

    def test_own_echo_does_not_mark_seen(self):
        link = HomeBotLink(broker="", autostart=False)
        msg = MagicMock()
        msg.topic = "saturday/saturday_homebot_01/status"
        msg.payload = b'{"type": "status_request"}'
        link._on_message(None, None, msg)
        self.assertFalse(link.connected)
        self.assertEqual(link.status()["link"], "never")
        # Genuine telemetry DOES mark seen.
        msg2 = MagicMock()
        msg2.topic = "saturday/saturday_homebot_01/telemetry"
        msg2.payload = b'{"sensors": {"batt": 90}}'
        link._on_message(None, None, msg2)
        self.assertTrue(link.connected)
        self.assertEqual(link.status()["link"], "live")
        self.assertEqual(link.status()["sensors"], {"batt": 90})
        print("DONE: homebot echo-guard test passed.")


class TestLongRun(TestCase):
    def test_histories_bounded(self):
        from saturday.screen_operator import ScreenOperator
        op = ScreenOperator()
        for i in range(250):
            op._audit("t", str(i))
        self.assertLessEqual(len(op.history), 200)
        from saturday.agent import AgentRunner, AgentTask
        r = AgentRunner(operator=MagicMock(), store_fn=lambda c, t: "x")
        for i in range(60):
            t = AgentTask("g", [{"action": "done", "args": {}}])
            r.run(t)
        self.assertLessEqual(len(r.history), 50)
        print("DONE: history bounds test passed.")

    def test_brain_retries_after_cooldown(self):
        from saturday.brain import OllamaBrain
        b = OllamaBrain(model="m", timeout=2)
        b._available = False
        b._checked_at = time.time() - 61
        with patch.object(OllamaBrain, "_get", return_value={"models": [{"name": "m"}]}):
            self.assertTrue(b.available())
        print("DONE: brain retry test passed.")


if __name__ == "__main__":
    test_main(verbosity=2)
