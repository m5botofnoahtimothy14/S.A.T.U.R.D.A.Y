import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import edith as ed
print("gate 'edith, status' ->", ed.edith_addressed("edith, status"), flush=True)
print("gate 'open notepad' ->", ed.edith_addressed("open notepad"), flush=True)
print("strip ->", repr(ed.strip_address("Edith, what time is it?")), flush=True)
print("*** EDITH SPEAKING NOW (female voice) ***", flush=True)
print("voiced:", ed.edith_say(None, "EDITH here. Same mind, at your service."), flush=True)
from unittest.mock import MagicMock
core = MagicMock()
core.process_command.return_value = "Status: ONLINE. Vault mounted."
print("handle:", ed.edith_handle(core, "edith status")[:80], flush=True)
print("DONE", flush=True)
