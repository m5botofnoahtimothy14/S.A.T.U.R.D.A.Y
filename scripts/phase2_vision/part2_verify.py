import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import senses
from saturday.session import CameraService, SessionManager

# 1. open_camera fallback
cap, backend, idx = senses.open_camera()
ok, f = cap.read()
print(f"OPEN: {backend}/{idx} frame={f.shape[1]}x{f.shape[0]} mean={f.mean():.1f}", flush=True)
cap.release()

# 2. CameraService live
cam = CameraService(fps=8.0)
cam.start()
time.sleep(4.0)
print("SERVICE:", cam.status(), "backend=", getattr(cam, "backend", "?"), flush=True)
fr = cam.get_frame()
print("FRAME:", None if fr is None else f"{fr.shape[1]}x{fr.shape[0]} mean={fr.mean():.1f}", flush=True)

# 3. mood_live throttle + smoothing behavior (no face -> honest, cached)
senses.mood_reset()
t0 = time.time()
r1 = senses.mood_live(fr)
r2 = senses.mood_live(fr)  # within 250ms -> cached
print(f"LIVE1: success={r1.get('success')} err={r1.get('error')} dt={(time.time()-t0)*1000:.0f}ms", flush=True)
print(f"LIVE2 cached: {r2 == r1}", flush=True)

# 4. smoothing vote logic with stubbed raw mood
calls = {"n": 0}
real = senses.mood
labels = ["happy", "happy", "sad", "happy", "happy"]
def fake(frame, model_path=None):
    calls["n"] += 1
    lab = labels[min(calls["n"] - 1, len(labels) - 1)]
    return {"success": True, "mood": lab, "confidence": 0.8,
            "top_emotion": lab, "scores": {}, "face": {}}
senses.mood = fake
senses.mood_reset()
for _ in range(5):
    senses._mood_last_run = 0  # bypass throttle
    out = senses.mood_live(fr)
print(f"SMOOTH: mood={out['mood']} votes={out['votes']} stability={out['stability']}", flush=True)
assert out["mood"] == "happy" and out["votes"] == {"happy": 4, "sad": 1}, "vote failed"
senses.mood = real

# 5. dashboard /api/mood + status payload wiring (fake session, no camera needed)
from unittest.mock import MagicMock
core = MagicMock()
core.session = MagicMock()
core.session.last_mood = {"mood": "happy", "confidence": 0.82, "stability": 0.8, "at": time.time() - 3}
from saturday.dashboard import _mood_payload
ref = MagicMock()
ref.core = core
print("MOOD_PAYLOAD:", _mood_payload(ref), flush=True)
cam.stop()
print("ALL PART2 CODE CHECKS DONE", flush=True)
