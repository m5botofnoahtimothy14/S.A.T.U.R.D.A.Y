"""SATURDAY official birth — first real boot on the hardened build.
Temp vault (nothing personal touched), real session boot, full
inspection, orderly shutdown. Every line below is live system output.
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from saturday.saturday_core import SATURDAYCore

tmp = Path(tempfile.mkdtemp(prefix="saturday_birth_"))
core = SATURDAYCore(passphrase="BirthDayPass123!", project_root=tmp)
core.initialize()
print("...letting services warm up (20s)...", flush=True)
time.sleep(20.0)

for cmd in ("doctor", "status", "resources", "humanoid status",
            "brain status", "neural roster", "eq"):
    print(f"\n❯ {cmd}", flush=True)
    try:
        print(core.process_command(cmd, trusted=True)[:1200], flush=True)
    except Exception as e:
        print(f"command crashed (must never happen): {e}", flush=True)

core.shutdown()
print("\n🌅 SATURDAY BIRTH COMPLETE — shutdown was orderly.", flush=True)
