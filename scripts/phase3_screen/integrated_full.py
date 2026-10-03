import sys, time, glob, os
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
try:
    import psutil as _ps
    mem = lambda: round(_ps.Process().memory_info().rss / 1048576, 1)
except Exception:
    mem = lambda: -1

def stage(name, fn):
    t0 = time.time()
    try:
        out = fn()
        print(f"[{name}] {time.time()-t0:.1f}s RAM={mem()}MB :: {out}", flush=True)
    except Exception as e:
        print(f"[{name}] FAILED: {str(e)[:150]}", flush=True)

from saturday import ears, senses
from saturday.session import CameraService, SessionManager
from saturday.screen_operator import ScreenOperator
from saturday.agent import AgentRunner, AgentTask, TemplateBrain, KillSwitch, clear_stop
from unittest.mock import MagicMock
import numpy as np

print(f"boot RAM={mem()}MB", flush=True)
wavs = sorted(glob.glob(r"D:\SATURDAY_TEMP\saturday_hear_*.wav"), key=os.path.getmtime)
stage("hear(base)", lambda: repr(ears.transcribe(wav_path=wavs[-1], language="en").get("text")))

cam = CameraService(fps=8.0); cam.start(); time.sleep(3.0)
mgr = SessionManager(MagicMock()); mgr.camera = cam
senses.mood_reset()
def _see():
    obs = mgr.observe()
    fr = cam.get_frame()
    who = "nobody"
    if fr is not None:
        fd = senses.find_faces(fr)
        if fd.get("boxes"):
            b = max(fd["boxes"], key=lambda r: r["w"] * r["h"])
            who = f"{len(fd['boxes'])} face(s) biggest={b['w']}x{b['h']}"
    return f"mood={obs.get('mood')} conf={obs.get('mood_confidence')} | {who} | ctx={mgr.mood_context()}"
stage("see(face+mood)", _see)

op = ScreenOperator()
def _screen():
    s = op.screenshot(r"D:\integrated2.png")
    rd = op.read_screen(s["path"]) if s.get("success") else {}
    fw = op.file_write(r"D:\SATURDAY_TEMP\integrated_ok.txt", "integration ok", confirm=True)
    return f"shot={s.get('width')}x{s.get('height')} words={len(rd.get('words', []))} file={fw.get('success')}"
stage("screen+ocr+file", _screen)

def _agent():
    clear_stop()
    mop = MagicMock()
    mop.screenshot.return_value = {"success": True, "path": "p"}
    mop.screen_size.return_value = {"success": True, "width": 1, "height": 1}
    mop.active_title.return_value = "Test"
    r = AgentRunner(operator=mop, brain=TemplateBrain(),
                    store_fn=lambda c, t: "x",
                    context_fn=lambda: mgr.mood_context(), max_steps=15)
    t = r.run(AgentTask("shot then done", [{"action": "screenshot", "args": {}},
                                           {"action": "done", "args": {}}]))
    return f"status={t.status} steps={len(t.transcript)} ctx_in_obs={'context' in str(t.transcript)}"
stage("agent(observe-verify)", _agent)

ks = KillSwitch()
stage("killswitch", lambda: f"armed={ks.start()}")
ks.stop()
cam.stop()
print(f"end RAM={mem()}MB", flush=True)
print("DONE", flush=True)
