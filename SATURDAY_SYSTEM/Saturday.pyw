"""SATURDAY silent launcher — double-click (or autostart) me.

Runs under pythonw.exe: NO console window appears. A passphrase dialog
pops, the core boots headless, the Control Center opens in your browser,
and SATURDAY settles into the system tray. Logs → logs/saturday.log.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
os.chdir(str(Path(__file__).parent.resolve()))

if __name__ == "__main__":
    from main import initialize_logging
    initialize_logging(os.getenv("SATURDAY_LOG_LEVEL", "INFO"))
    from saturday.tray import run
    run()
