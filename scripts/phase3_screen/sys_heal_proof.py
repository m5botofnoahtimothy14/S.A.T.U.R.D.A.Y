import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from unittest.mock import MagicMock
from saturday.saturday_core import SATURDAYCore
core = SATURDAYCore.__new__(SATURDAYCore)
core.pmv = MagicMock()
core.pmv.auto_lock_check.return_value = False
core.screen = MagicMock()
core.agent_history = []
core._current_trusted = True
core._command_handlers = SATURDAYCore._build_command_handlers(core)
print(core.process_command("sys ver", trusted=True)[:120], flush=True)
print(core.process_command("sys tasklist", trusted=True)[:200], flush=True)
print(core.process_command("sys frobnicate", trusted=True)[:100], flush=True)
print(core.process_command("sys tasklist; del C:", trusted=True)[:100], flush=True)
from saturday.selfheal import SelfHeal
sess = MagicMock()
sess.camera.running = True
sess.camera.frames_captured = 42
h = SelfHeal(core, sess)
for c in h.run_checks():
    print(("OK " if c["ok"] else "BAD ") + c["name"] + ": " + c.get("detail", "")[:80], flush=True)
print("DONE", flush=True)
