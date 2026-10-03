import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
try:
    import psutil as _ps
    _mem = lambda: round(_ps.Process().memory_info().rss / 1048576, 1)
except Exception:
    _mem = lambda: -1
print(f"RAM start: {_mem()} MB", flush=True)

from saturday import senses
from saturday.session import CameraService, SessionManager
from unittest.mock import MagicMock

# -- integrated 1b: face -> mood (hearing part needs live voice, self-serve)
t0 = time.time()
cam = CameraService(fps=8.0); cam.start(); time.sleep(3.0)
mgr = SessionManager(MagicMock()); mgr.camera = cam
senses.mood_reset()
obs = mgr.observe()
print(f"MOOD stage: {time.time()-t0:.1f}s RAM={_mem()}MB obs_mood={obs.get('mood')} "
      f"conf={obs.get('mood_confidence')} last={mgr.last_mood}", flush=True)

# -- integrated 3: screenshot + what's on screen
from saturday.screen_operator import ScreenOperator
op = ScreenOperator()
t0 = time.time()
shot = op.screenshot(r"D:\integrated_screen.png")
rd = op.read_screen(shot["path"]) if shot.get("success") else {}
txt = rd.get("words", [])
print(f"SCREEN stage: {time.time()-t0:.1f}s RAM={_mem()}MB shot={shot.get('width')}x{shot.get('height')} "
      f"words={len(txt)}", flush=True)
tops = " | ".join(w["text"] for w in sorted(txt, key=lambda w: -w.get("conf", 0))[:25])
print("TOP OCR:", tops[:300], flush=True)

# -- brain vision available?
try:
    from saturday.brain import OllamaBrain
    print("BRAIN ollama available:", OllamaBrain().available(), flush=True)
except Exception as e:
    print("BRAIN check failed:", str(e)[:100], flush=True)

# -- integrated 5: kill switch armed?
from saturday.agent import KillSwitch, stop_requested
ks = KillSwitch()
print("KILL armed:", ks.start(), "| stop_requested:", stop_requested(), flush=True)
ks.stop()
cam.stop()
print(f"RAM end: {_mem()} MB", flush=True)
print("DONE", flush=True)
