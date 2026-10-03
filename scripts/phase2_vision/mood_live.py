import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import senses
from saturday.session import CameraService, SessionManager
from unittest.mock import MagicMock

cam = CameraService(fps=8.0)
cam.start()
time.sleep(3.0)
print("CAM:", cam.status(), flush=True)

mgr = SessionManager(MagicMock())
mgr.camera = cam
senses.mood_reset()
t0 = time.time()
last = ""
# 24s window: neutral -> smile -> surprised
while time.time() - t0 < 24.0:
    el = time.time() - t0
    obs = mgr.observe()
    m = obs.get("mood", "?")
    if m != last:
        print(f"t={el:4.1f}s mood -> {m} conf={obs.get('mood_confidence')} "
              f"stab={obs.get('mood_stability')} err={obs.get('mood_error')}", flush=True)
        last = m
    time.sleep(0.5)
print("LAST_MOOD (dashboard /api/mood source):", mgr.last_mood, flush=True)
print("MOOD_CONTEXT (brain/agent line):", mgr.mood_context(), flush=True)
cam.stop()
print("DONE", flush=True)
