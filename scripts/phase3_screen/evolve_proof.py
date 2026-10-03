import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from unittest.mock import MagicMock
from saturday.saturday_core import SATURDAYCore

# pure diff machinery
orig = "a = 1\nb = 2\nc = 3\n"
diff = "--- a/x.py\n+++ b/x.py\n@@ -1,3 +1,3 @@\n a = 1\n-b = 2\n+b = 22\n c = 3\n"
print("APPLY:", repr(SATURDAYCore._apply_diff(orig, diff)), flush=True)
print("EXTRACT:", repr(SATURDAYCore._extract_diff("here\n```diff\n" + diff + "```\ntail")[:60]), flush=True)
try:
    SATURDAYCore._apply_diff(orig, diff.replace("b = 2", "b = 9"))
    print("MISMATCH: NOT caught (bad)", flush=True)
except ValueError as e:
    print("MISMATCH caught:", e, flush=True)

core = SATURDAYCore.__new__(SATURDAYCore)
core.pmv = MagicMock()
core.pmv.auto_lock_check.return_value = False
core.screen = MagicMock()
core.agent_history = []
core._current_trusted = True
core._command_handlers = SATURDAYCore._build_command_handlers(core)
print("outside:", core.process_command("evolve C:\\Windows\\x.py change", trusted=True)[:70], flush=True)
print("nonpy:", core.process_command("evolve README.md change it", trusted=True)[:70], flush=True)
print("sysclean staged?", "sysclean" in core._command_handlers, flush=True)
print("DONE", flush=True)
