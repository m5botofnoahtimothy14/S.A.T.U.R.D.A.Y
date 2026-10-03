import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from unittest.mock import MagicMock
from saturday.saturday_core import SATURDAYCore
from saturday import verse
core = SATURDAYCore.__new__(SATURDAYCore)
core.pmv = MagicMock()
core.pmv.auto_lock_check.return_value = False
core.screen = MagicMock()
core.agent_history = []
core._current_trusted = True
core._command_handlers = SATURDAYCore._build_command_handlers(core)

def ok(**kw):
    d = {"success": True}
    d.update(kw)
    return d
core.screen.volume.return_value = ok(action="up")
core.screen.media.return_value = ok(action="playpause")
print("volume:", core.process_command("volume up", trusted=True), flush=True)
print("play:", core.process_command("play", trusted=True), flush=True)
print("verse:", core.process_command("verse", trusted=True)[:80], flush=True)
print("verse23:", core.process_command("verse 23:1", trusted=True)[:80], flush=True)
core.screen.read_screen.return_value = ok(path="p", text="Hello world test", words=[{"text": "Hello"}])
core._speak = MagicMock()
print("tell:", core.process_command("tell", trusted=True)[:100], flush=True)
print("speak called:", core._speak.called, flush=True)
# presence watch snapshot with synthetic frame
import numpy as np
from saturday.presence import PresenceLoop
sess = MagicMock()
loop = PresenceLoop.__new__(PresenceLoop)
loop.session = sess
loop._last_watch = 0.0
import time
p = loop._watch_snapshot(np.full((100, 100, 3), 128, dtype=np.uint8))
print("watch snapshot:", p, flush=True)
import os
print("exists:", os.path.exists(p) if p else False, flush=True)
print("DONE", flush=True)
