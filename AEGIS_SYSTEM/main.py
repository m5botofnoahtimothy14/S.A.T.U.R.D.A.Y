#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║                    AEGIS INTELLIGENCE SYSTEM                     ║
║              Autonomous Encrypted Guardian & Intelligence        ║
║                    with Private Memory Vault                     ║
╠══════════════════════════════════════════════════════════════════╣
║  AEGIS = Brain  (reasoning, commands, orchestration)             ║
║  PMV   = Memory (encrypted storage, secrets, logs)               ║
║  Together = Autonomous Private Intelligence System               ║
╚══════════════════════════════════════════════════════════════════╝

No cloud dependency. No external APIs. Fully self-hosted.
"""

import sys
import os
import signal
import getpass
import atexit
import ctypes
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from aegis.aegis_core import AEGISCore
from interface.cli import AEGISCLI

# ─────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-18s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AEGIS.Main")


def _secure_clear_string(s: str) -> None:
    """Best-effort secure clearing of a string from memory."""
    try:
        # Overwrite the string buffer in memory (CPython-specific)
        str_addr = id(s)
        str_len = len(s)
        if str_len > 0:
            ctypes.memset(str_addr + sys.getsizeof("") - 1, 0, str_len)
    except Exception:
        pass  # Not all platforms support this


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
    """Main entry point for the AEGIS Intelligence System."""
    print(BANNER)
    logger.info("AEGIS Intelligence System starting...")

    # ── Session passphrase ──────────────────────────
    passphrase = None
    try:
        print("  ┌─────────────────────────────────────────────┐")
        print("  │  🔐 AUTHENTICATION REQUIRED                 │")
        print("  │  Enter your vault passphrase to proceed.    │")
        print("  │  This passphrase is NEVER stored to disk.   │")
        print("  └─────────────────────────────────────────────┘")
        print()
        passphrase = getpass.getpass("  🔑 Vault Passphrase: ")

        if not passphrase or len(passphrase) < 8:
            print("\n  ❌ Passphrase must be at least 8 characters.")
            sys.exit(1)

        confirm = getpass.getpass("  🔑 Confirm Passphrase: ")
        if passphrase != confirm:
            print("\n  ❌ Passphrases do not match.")
            _secure_clear_string(confirm)
            _secure_clear_string(passphrase)
            sys.exit(1)
        _secure_clear_string(confirm)

        # ── Initialize AEGIS Core ───────────────────
        logger.info("Initializing AEGIS Core with PMV Memory System...")
        core = AEGISCore(passphrase=passphrase, project_root=PROJECT_ROOT)

        # Clear passphrase from local scope after core has derived keys
        _secure_clear_string(passphrase)
        passphrase = None

        # ── Register shutdown handlers ──────────────
        def shutdown_handler(signum=None, frame=None):
            logger.info("Shutdown signal received. Securing system...")
            core.shutdown()
            logger.info("AEGIS system secured and stopped.")
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)
        atexit.register(core.shutdown)

        # ── Start AEGIS ─────────────────────────────
        core.initialize()
        logger.info("AEGIS Core initialized successfully.")

        # ── Launch CLI Interface ────────────────────
        cli = AEGISCLI(core)
        cli.run()

    except KeyboardInterrupt:
        print("\n\n  ⚠️  Interrupted. Shutting down securely...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n  ❌ Fatal error: {e}")
    finally:
        # Ensure passphrase is cleared even on error
        if passphrase is not None:
            _secure_clear_string(passphrase)
        logger.info("AEGIS system terminated.")


if __name__ == "__main__":
    main()
