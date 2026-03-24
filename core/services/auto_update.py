# services/auto_update.py
import subprocess
import logging
import threading
import time
import os

logger = logging.getLogger("AEGIS.Services.AutoUpdate")

class AutoUpdateService:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._check_loop, daemon=True).start()
        logger.info("Auto-Update service started.")

    def _check_loop(self):
        while self.running:
            try:
                logger.info("Checking for AEGIS system updates...")
                fetch = subprocess.run(
                    ["git", "fetch", "--prune"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=os.getcwd(),
                )
                if fetch.returncode != 0:
                    logger.warning("Git fetch failed: %s", fetch.stderr.strip())
                else:
                    status = subprocess.run(
                        ["git", "status", "-uno"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=os.getcwd(),
                    )
                    logger.info("Update status: %s", status.stdout.strip() or "up to date")
                    if os.getenv("AEGIS_AUTO_UPDATE_APPLY", "false").strip().lower() in {"1", "true", "yes", "on"}:
                        pull = subprocess.run(
                            ["git", "pull", "--ff-only"],
                            capture_output=True,
                            text=True,
                            timeout=120,
                            cwd=os.getcwd(),
                        )
                        if pull.returncode != 0:
                            logger.warning("Git pull failed: %s", pull.stderr.strip())
                        else:
                            logger.info("Applied update: %s", pull.stdout.strip())
                time.sleep(3600) # Check every hour
            except Exception as e:
                logger.error(f"Auto-update check failed: {e}")
