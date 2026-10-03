import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from unittest.mock import MagicMock
from saturday import humanvoice as hv
from saturday.saturday_core import SATURDAYCore

print("family wife:", hv.family_line("khadija", "wife")[:70], flush=True)
print("family work:", hv.family_line("khadija", "gf", "work")[:70], flush=True)
print("work sir:", hv.arrival_line("sir", None, "work"), flush=True)

core = SATURDAYCore.__new__(SATURDAYCore)
core.pmv = MagicMock()
core.pmv.auto_lock_check.return_value = False
core.screen = MagicMock()
core.agent_history = []
core.workmode = False
core._current_trusted = True
core._command_handlers = SATURDAYCore._build_command_handlers(core)
print("owner:", core._owner_name(), flush=True)
print("workmode:", core.process_command("workmode on", trusted=True), flush=True)
print("workmode flag:", core.workmode, flush=True)
print("MEM remember:", core.process_command("remember my wife's name is khadija", trusted=True), flush=True)
core.pmv.secure_search.return_value = [{"content": "my wife's name is khadija", "timestamp": 1, "tags": ["profile-fact"]}]
print("MEM recall:", core.process_command("recall wife", trusted=True)[:90], flush=True)
print("MEM profile:", core.process_command("profile", trusted=True)[:90], flush=True)

from interface.voice import SATURDAYVoice
v = SATURDAYVoice(core=None)
print("*** EDITH (Noah + pauses) SPEAKING - listen ***", flush=True)
v.speak("Mmm... Noah... you called? ... I'm here.", voice="edith")
print("*** SATURDAY workmode (sir) SPEAKING - listen ***", flush=True)
v.speak("sir. Focused. What do you need?")
print("DONE", flush=True)
