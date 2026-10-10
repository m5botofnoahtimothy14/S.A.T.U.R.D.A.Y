"""Localhost backup audit — every dashboard endpoint, token-authed.
Run anytime: python scripts/localhost_audit.py
Exit 0 = all green. Anything red tells you the exact route + reason.
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8099"
TOKEN = "NzR8CqB0hWKmPehNUt7auROKcz4lTgMoIuFyrJZ6"

PASS, FAIL = [], []


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json",
                 "X-Saturday-Token": TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode()[:400]
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read().decode()[:400]
        except Exception:
            return e.code, ""
    except Exception as e:
        return -1, str(e)[:200]


def check(name, method, path, body=None, want=(200,), must_contain=""):
    code, text = call(method, path, body)
    ok = code in want and (must_contain in text if must_contain else True)
    (PASS if ok else FAIL).append(name)
    print(f"{'PASS' if ok else 'FAIL'} {name} [{code}] {text[:100]}")


def main():
    # unauthed must be refused (tunnel safety)
    try:
        req = urllib.request.Request(BASE + "/api/status", method="GET")
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"FAIL no-auth-open [{r.status}] (token gate bypassed!)")
            FAIL.append("token-gate")
    except urllib.error.HTTPError as e:
        ok = e.code == 403
        (PASS if ok else FAIL).append("token-gate")
        print(f"{'PASS' if ok else 'FAIL'} token-gate [{e.code}]")
    except Exception as e:
        FAIL.append("token-gate")
        print(f"FAIL token-gate [unreachable: {e}]")
        print("RESULT: dashboard not reachable at all")
        return 1

    check("status", "GET", "/api/status", must_contain="online")
    check("health", "GET", "/api/health", must_contain="healthy")
    check("tasks", "GET", "/api/tasks")
    check("log", "GET", "/api/log")
    check("frame", "GET", "/api/frame")
    check("miclevel", "GET", "/api/miclevel")
    check("mood", "GET", "/api/mood")
    check("gallery", "POST", "/api/gallery", {})
    check("command/status", "POST", "/api/command", {"command": "status"})
    check("command/doctor", "POST", "/api/command", {"command": "doctor"})
    check("command/resources", "POST", "/api/command", {"command": "resources"})
    check("command/services", "POST", "/api/command", {"command": "services"})
    check("command/server", "POST", "/api/command", {"command": "server"})
    check("command/mailbox", "POST", "/api/command", {"command": "mailbox"})
    check("command/neural-roster", "POST", "/api/command", {"command": "neural roster"})
    check("command/humanoid-status", "POST", "/api/command", {"command": "humanoid status"})
    check("camera/start", "POST", "/api/camera/start")
    check("camera/stop", "POST", "/api/camera/stop")
    check("homebot", "POST", "/api/homebot",
          {"command": "stop", "duration": 0.5, "speed": 50})
    check("task/add", "POST", "/api/task/add",
          {"goal": "localhost audit ping", "priority": 3})
    check("forget-missing", "POST", "/api/forget_person",
          {"name": "Nobody Here"}, must_contain="success")
    print(f"\nRESULT: {len(PASS)} green, {len(FAIL)} red"
          + (f" ({', '.join(FAIL)})" if FAIL else " — localhost backup READY"))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
