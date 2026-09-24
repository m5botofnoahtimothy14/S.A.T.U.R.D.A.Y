#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║                    SATURDAY INTELLIGENCE SYSTEM                     ║
║              Autonomous Encrypted Guardian & Intelligence        ║
║                    with Private Memory Vault                     ║
╠══════════════════════════════════════════════════════════════════╣
║  SATURDAY = Brain  (reasoning, commands, orchestration)             ║
║  PMV   = Memory (encrypted storage, secrets, logs)               ║
║  Together = Autonomous Private Intelligence System               ║
╚══════════════════════════════════════════════════════════════════╝

No cloud dependency. No external APIs. Fully self-hosted.
"""

import argparse
import sys
import os
import signal
import getpass
import atexit
import ctypes
import logging
import json
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller one-dir: live next to the exe (vault/config/dashboard
    # resolve beside SATURDAY.exe, not inside _internal).
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).parent.resolve()
    sys.path.insert(0, str(PROJECT_ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass  # dotenv is optional; env vars can be set directly

from saturday.saturday_core import SATURDAYCore
from interface.cli import SATURDAYCLI
from realtime_bridge import RealtimeDatabaseBridge

LOG_FORMAT = "%(asctime)s │ %(name)-18s │ %(levelname)-7s │ %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger("SATURDAY.Main")


def initialize_logging(level: str = "INFO"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=DATE_FORMAT)
    logger.setLevel(level)
    return logger


def _secure_clear_string(value: str) -> None:
    try:
        addr = id(value)
        length = len(value)
        if length > 0:
            ctypes.memset(addr + sys.getsizeof("") - 1, 0, length)
    except Exception:
        pass


def run_smoke() -> int:
    """Frozen-exe self-test: full vault E2E in temp dirs, no user input."""
    import shutil
    import tempfile

    print("SATURDAY self-test (temp dirs, nothing touched)...")
    tmp = Path(tempfile.mkdtemp(prefix="saturday_smoke_"))
    try:
        core = SATURDAYCore(passphrase="SmokeTestPass123!", project_root=tmp)
        core.initialize()
        out = core.process_command("store smoke payload tag:smoke")
        assert "Stored securely" in out, out
        entry_id = out.rsplit(":", 1)[-1].strip()
        out = core.process_command(f"retrieve {entry_id}")
        assert "smoke payload" in out, out
        payload = core.get_status_payload()
        assert payload["online"] and payload["vault_mounted"], payload
        core.shutdown()
        print("SMOKE: PASS (vault E2E + status, frozen boot OK)")
        return 0
    except Exception as e:
        print(f"SMOKE: FAIL: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


def create_realtime_bridge(args: argparse.Namespace):
    service_account = args.service_account or os.getenv("FIREBASE_SERVICE_ACCOUNT", "")
    node_id = args.node_id or os.getenv("FIREBASE_NODE_ID", "saturday-node")
    if not service_account or not database_url:
        raise RuntimeError("Firebase realtime requires FIREBASE_SERVICE_ACCOUNT and FIREBASE_DATABASE_URL.")
    return RealtimeDatabaseBridge(service_account=service_account, database_url=database_url, node_id=node_id)


def prompt_passphrase() -> str:
    print("  ┌─────────────────────────────────────────────┐")
    print("  │  🔐 AUTHENTICATION REQUIRED                 │")
    print("  │  Enter your vault passphrase to proceed.    │")
    print("  │  This passphrase is NEVER stored to disk.   │")
    print("  └─────────────────────────────────────────────┘")
    print()
    first = getpass.getpass("  🔑 Vault Passphrase: ")
    if not first or len(first) < 8:
        raise ValueError("Passphrase must be at least 8 characters.")
    second = getpass.getpass("  🔑 Confirm Passphrase: ")
    if first != second:
        _secure_clear_string(second)
        raise ValueError("Passphrases do not match.")
    _secure_clear_string(second)
    return first


BANNER = r"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║     █████╗ ███████╗ ██████╗ ██╗███████╗                         ║
║    ██╔══██╗██╔════╝██╔════╝ ██║██╔════╝                         ║
║    ███████║█████╗  ██║  ███╗██║███████╗                          ║
║    ██╔══██║██╔══╝  ██║   ██║██║╚════██║                          ║
║    ██║  ██║███████╗╚██████╔╝██║███████║                          ║
║    ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝╚══════╝                        ║
║                                                                  ║
║       Autonomous Encrypted Guardian Intelligence System          ║
║              with Private Memory Vault (PMV)                     ║
║                                                                  ║
║    ● Fully Self-Hosted   ● Zero Cloud Dependency                 ║
║    ● Layered Encryption  ● Dead-Man Switch                       ║
║    ● Multi-Device Sync   ● Local Intelligence                    ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""


def main():
    parser = argparse.ArgumentParser(description="SATURDAY PMV Runtime")
    parser.add_argument("--firebase-realtime", action="store_true", help="Enable Firebase realtime status and remote command processing.")
    parser.add_argument("--service-account", help="Path to Firebase service account JSON file.")
    parser.add_argument("--database-url", help="Firebase Realtime Database URL.")
    parser.add_argument("--node-id", help="Node ID used for realtime updates.")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    parser.add_argument("--smoke", action="store_true",
                        help="Self-test: temp-dir vault E2E + status, no passphrase needed.")
    args = parser.parse_args()

    initialize_logging(args.log_level.upper())
    if args.smoke:
        return run_smoke()
    print(BANNER)
    logger.info("SATURDAY Intelligence System starting...")

    if getattr(sys, "frozen", False):
        # First run beside the exe: seed user config from bundled defaults
        # so vault/config live OUTSIDE _internal (survive rebuilds).
        try:
            import shutil

            meipass = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
            for name in ("settings.json",):
                src = meipass / "config" / name
                dst = PROJECT_ROOT / "config" / name
                if not dst.exists() and src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src, dst)
                    logger.info(f"Seeded {dst} from bundled defaults.")
        except Exception as e:
            logger.warning(f"Config seeding skipped: {e}")

    passphrase = None
    core = None
    realtime_bridge = None
    _shutdown_done = False

    def shutdown_system():
        nonlocal _shutdown_done
        if _shutdown_done:
            return
        _shutdown_done = True
        if realtime_bridge:
            try:
                realtime_bridge.stop()
            except Exception:
                pass
        if core:
            core.shutdown()
            try:
                if hasattr(core.pmv, "clear_credentials"):
                    core.pmv.clear_credentials()
            except Exception:
                pass
        logger.info("SATURDAY system secured and stopped.")

    def shutdown_handler(signum=None, frame=None):
        logger.info("Shutdown signal received.")
        shutdown_system()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    try:
        signal.signal(signal.SIGTERM, shutdown_handler)
    except (AttributeError, ValueError, OSError):
        pass  # SIGTERM unavailable on some Windows configs
    atexit.register(shutdown_system)

    try:
        passphrase = prompt_passphrase()
        core = SATURDAYCore(passphrase=passphrase, project_root=PROJECT_ROOT)
        core.initialize()
        logger.info("SATURDAY Core initialized successfully.")

        if args.firebase_realtime or (os.getenv("FIREBASE_SERVICE_ACCOUNT") and os.getenv("FIREBASE_DATABASE_URL")):
            try:
                realtime_bridge = create_realtime_bridge(args)
                realtime_bridge.start(
                    lambda: core.get_status_payload(),
                    # Remote commands are untrusted: screen-driving is refused.
                    lambda command_text, metadata: core.process_command(command_text, trusted=False),
                )
            except Exception as exc:
                logger.warning(f"Realtime bridge unavailable: {exc}")

        cli = SATURDAYCLI(core)
        cli.run()

    except KeyboardInterrupt:
        print("\n\n  ⚠️  Interrupted. Shutting down securely...")
    except ValueError as exc:
        print(f"\n  ❌ {exc}")
        logger.warning(str(exc))
    except Exception as exc:
        logger.exception("Fatal startup error")
        print(f"\n  ❌ Fatal error: {exc}")
    finally:
        if passphrase is not None:
            _secure_clear_string(passphrase)
        shutdown_system()
        logger.info("SATURDAY system terminated.")


if __name__ == "__main__":
    main()
