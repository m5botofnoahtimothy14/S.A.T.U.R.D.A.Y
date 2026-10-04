"""SATURDAY serve — the always-on server. Uptime until the kill switch.

Boot:  python serve.py [--port 8099] [--tunnel] [--realtime]
  Passphrase via getpass (your terminal, never stored) or SATURDAY_PASS env.
Starts: core + vault + camera hub + mind + presence + dashboard HUD (localhost),
optionally the cloudflared tunnel (for Vercel) and Firebase realtime bridge
(when FIREBASE_SERVICE_ACCOUNT + FIREBASE_DATABASE_URL are set).

Kill switch (ANY of these halts everything, vault dismounts):
  Ctrl+C here, voice "stop", global hotkey Ctrl+Alt+Shift+X,
  or: echo stop > D:\\SATURDAY_TEMP\\saturday.stop
Logs: D:\\SATURDAY_TEMP\\serve.log (C: untouched).
"""

import getpass
import logging
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("SATURDAY_D_TMP", r"D:\SATURDAY_TEMP")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(),
              logging.FileHandler(r"D:\SATURDAY_TEMP\serve.log", encoding="utf-8")])
logger = logging.getLogger("SATURDAY.Serve")

STOP_FILE = Path(r"D:\SATURDAY_TEMP\saturday.stop")


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="SATURDAY always-on server")
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--tunnel", action="store_true",
                    help="expose HUD via cloudflared (URL goes to Vercel SAT_API)")
    ap.add_argument("--realtime", action="store_true",
                    help="Firebase realtime bridge (needs env credentials)")
    args = ap.parse_args()

    from saturday.saturday_core import SATURDAYCore
    from saturday.session import SessionManager

    pw = os.getenv("SATURDAY_PASS", "")
    if not pw:
        pw = getpass.getpass("Vault passphrase (never stored): ")
    if len(pw) < 8:
        print("Passphrase must be at least 8 characters.")
        return 2
    core = SATURDAYCore(passphrase=pw, project_root=PROJECT_ROOT)
    del pw
    _sa = os.getenv("FIREBASE_SERVICE_ACCOUNT", "")
    _db = os.getenv("FIREBASE_DATABASE_URL", "")
    if _sa or _db:
        core.cloud_config = {"service_account": _sa, "database_url": _db,
                             "node": os.getenv("FIREBASE_NODE_ID", "saturday-node")}
    core.initialize()

    session = SessionManager(core)
    core.session = session
    session.boot()
    logger.warning("SATURDAY serve: session booting (camera/mind/presence/dashboard)...")

    # -- ordered startup procedure: each leg reports ready in sequence --
    def _stage(label, fn, timeout):
        import time as _t

        t0 = _t.time()
        while _t.time() - t0 < timeout:
            try:
                detail = fn()
                if detail:
                    logger.warning(f"BOOT [ok] {label}: {detail} ({_t.time()-t0:.0f}s)")
                    print(f"  [ok] {label}: {detail}", flush=True)
                    return True
            except Exception:
                pass
            _t.sleep(1.0)
        logger.warning(f"BOOT [MISS] {label} after {timeout}s — continuing degraded")
        print(f"  [MISS] {label} — continuing degraded", flush=True)
        return False

    print("SATURDAY boot sequence:", flush=True)
    _stage("vault", lambda: "mounted" if core.pmv.vault_mounted else None, 10)
    _stage("camera", lambda: (f"{session.camera.frames_captured} frames"
                              if session.camera.running and session.camera.frames_captured else None), 40)
    _stage("ears/stt", lambda: "whisper hot" if session.stt_ready else None, 180)
    _stage("brain", lambda: ("ready" if session.brain_ready else "offline-fallback")
           if session.brain_ready is not None else None, 40)
    _stage("mind+presence", lambda: ("running" if (session.mind and session.mind.running
           and session.presence and session.presence.running) else None), 40)
    _stage("dashboard", lambda: session.dashboard_url or None, 40)

    try:
        from saturday.agent import KillSwitch, stop_requested

        KillSwitch().start()  # Ctrl+Alt+Shift+X halts from anywhere
    except Exception as e:
        logger.warning(f"kill-switch hotkey unavailable: {e}")

    # Firebase realtime rides with the session server (AlwaysOnServer reads
    # core.cloud_config / FIREBASE_* env itself). Nothing extra to start here.
    if args.realtime or (_sa and _db):
        logger.warning("realtime bridge: armed via session server (env creds present)")

    if args.tunnel:
        try:
            out = core.process_command(f"dashboard {args.port}", trusted=True)
            logger.warning(out)
            out = core.process_command("share on", trusted=True)
            logger.warning(out)
            print(out, flush=True)
        except Exception as e:
            logger.warning(f"tunnel failed: {e}")

    if STOP_FILE.exists():
        try:
            STOP_FILE.unlink()
        except Exception:
            pass
    logger.warning(f"HUD target: http://127.0.0.1:{args.port}/  (serve running until kill switch)")
    print(f"SATURDAY SERVING on http://127.0.0.1:{args.port}/ — kill: Ctrl+C, voice stop, hotkey, or stop-file",
          flush=True)
    try:
        while True:
            time.sleep(1.0)
            if STOP_FILE.exists():
                logger.warning("stop-file seen — halting")
                try:
                    from saturday import agent as _ag

                    _ag.request_stop()
                except Exception:
                    pass
                break
            try:
                from saturday import agent as _ag

                if _ag.stop_requested():
                    logger.warning("kill switch engaged — halting")
                    break
            except Exception:
                pass
    except KeyboardInterrupt:
        logger.warning("Ctrl+C — halting")
    finally:
        try:
            session.shutdown()
        except Exception:
            pass
        try:
            core.shutdown()
        except Exception:
            pass
        logger.warning("serve stopped, vault dismounted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
