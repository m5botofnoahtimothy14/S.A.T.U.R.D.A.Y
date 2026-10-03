"""Part 2 live vision probe: faces + ONNX mood + MediaPipe landmarker."""
import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
import cv2, numpy as np
from saturday import senses

print("== open DSHOW idx0 ==", flush=True)
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
print("opened:", cap.isOpened(), flush=True)
frames = []
t0 = time.time()
while time.time() - t0 < 8.0:
    ok, f = cap.read()
    if ok and f is not None:
        frames.append(f)
cap.release()
print(f"captured {len(frames)} frames in {time.time()-t0:.1f}s "
      f"({len(frames)/max(time.time()-t0,0.1):.1f} fps)", flush=True)

print("== Haar faces + ONNX mood ==", flush=True)
for i, f in enumerate(frames[:: max(1, len(frames)//4)][:4]):
    h, w = f.shape[:2]
    fd = senses.find_faces(f)
    print(f"frame{i}: shape={w}x{h} mean={f.mean():.1f} faces={fd}", flush=True)
    t1 = time.time()
    m = senses.mood(f)
    dt = (time.time() - t1) * 1000
    if m.get("success"):
        print(f"  MOOD={m['mood']} top={m['top_emotion']} conf={m['confidence']} "
              f"scores={m['scores']} infer_ms={dt:.0f}", flush=True)
    else:
        print(f"  mood FAIL: {m.get('error')} infer_ms={dt:.0f}", flush=True)

print("== MediaPipe face_landmarker.task ==", flush=True)
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
task_path = r"D:\S.A.T.U.R.D.A.Y\models\face_landmarker.task"
import os
print("task exists:", os.path.exists(task_path),
      "size:", os.path.getsize(task_path) if os.path.exists(task_path) else 0, flush=True)
base = mp_python.BaseOptions(model_asset_path=task_path)
opts = mp_vision.FaceLandmarkerOptions(
    base_options=base, running_mode=mp_vision.RunningMode.IMAGE,
    num_faces=1, output_face_blendshapes=True)
t1 = time.time()
with mp_vision.FaceLandmarker.create_from_options(opts) as lm:
    print(f"landmarker loaded in {(time.time()-t1)*1000:.0f}ms", flush=True)
    for i, f in enumerate(frames[:: max(1, len(frames)//3)][:3]):
        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        t2 = time.time()
        res = lm.detect(mp_img)
        dt = (time.time() - t2) * 1000
        n = len(res.face_landmarks)
        nl = len(res.face_landmarks[0]) if n else 0
        nb = len(res.face_blendshapes[0]) if res.face_blendshapes else 0
        print(f"frame{i}: faces={n} landmarks={nl} blendshapes={nb} infer_ms={dt:.0f}", flush=True)
print("DONE", flush=True)
