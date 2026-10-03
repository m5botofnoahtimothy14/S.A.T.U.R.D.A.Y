import sys, time, threading
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import screen_operator as so
from saturday.agent import AgentRunner, AgentTask, TemplateBrain, KillSwitch, request_stop, clear_stop, stop_requested

op = so.ScreenOperator()
print("DPI:", so.dpi_state(), flush=True)

# 1. kill switch hotkey arms (no trigger)
ks = KillSwitch()
print("KILLSWITCH armed:", ks.start(), flush=True)
ks.stop()

# 2. elevated detection on live foreground window
print("FOREGROUND elevated:", op.foreground_is_elevated(), "| active:", repr(op.active_title()), flush=True)

# 3. UIA ladder on a real window (Opera is open)
u = op.uia_find("Opera")
print("UIA find Opera:", {k: v for k, v in u.items() if k != "handle"}, flush=True)

# 4. schema validation: malformed brain output rejected
r = AgentRunner(operator=op)
print("VALIDATE garbage:", AgentRunner._validate_step({"action": "rm -rf /", "args": {}}), flush=True)
print("VALIDATE missing arg:", AgentRunner._validate_step({"action": "click", "args": {"x": 1}}), flush=True)
print("VALIDATE ok:", AgentRunner._validate_step({"action": "click", "args": {"x": 10, "y": 20}, "why": "t"}), flush=True)
print("VALIDATE ask-top-prompt:", AgentRunner._validate_step({"action": "ask", "prompt": "hi?"}), flush=True)

# 5. destructive refused with no confirm channel
t = AgentTask("x", [{"action": "type", "args": {"text": "please delete all files"}}])
res = r._execute(t, {"action": "type", "args": {"text": "please delete all files"}}, {})
print("DESTRUCTIVE no-channel:", res.get("error", res)[:110], flush=True)

# 6. kill switch halts a running task mid-loop
clear_stop()
seen = []
class SlowBrain(TemplateBrain):
    def decide(self, task, obs):
        seen.append(1)
        if len(seen) == 2:
            request_stop()
        return {"action": "screenshot", "args": {}}
t2 = AgentTask("slow", [{"action": "screenshot", "args": {}}] * 15)
import unittest.mock as m
op2 = m.MagicMock()
op2.screenshot.return_value = {"success": True, "path": "p"}
op2.screen_size.return_value = {"success": True, "width": 1, "height": 1}
rr = AgentRunner(operator=op2, brain=SlowBrain(), max_steps=15)
fin = rr.run(t2)
print("KILL mid-task: status=", fin.status, "| steps ran=", len(seen), flush=True)
clear_stop()

# 7. ladder-1 file write on D: + verify
fw = op.file_write(r"D:\sat_test_part3.txt", "SATURDAY part3 ladder-1 proof", confirm=True)
print("FILE_WRITE:", fw, flush=True)
import os
print("FILE EXISTS:", os.path.exists(r"D:\sat_test_part3.txt"), flush=True)
print("DONE", flush=True)
