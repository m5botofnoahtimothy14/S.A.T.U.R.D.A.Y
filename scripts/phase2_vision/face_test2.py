import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
import cv2
from saturday import senses
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
frames = []
t0 = time.time()
while time.time() - t0 < 12.0:
    ok, f = cap.read()
    if ok and f is not None:
        frames.append(f)
cap.release()
print(f"n={len(frames)}", flush=True)
mid = frames[len(frames)//2]
cv2.imwrite(r"D:\face_debug.jpg", mid)
print(f"saved D:\\face_debug.jpg shape={mid.shape[1]}x{mid.shape[0]} mean={mid.mean():.1f}", flush=True)
fd = senses.find_faces(mid)
print("HAAR:", fd, flush=True)
m = senses.mood(mid)
print("MOOD:", {k: v for k, v in m.items() if k != "scores"}, "scores:", m.get("scores"), flush=True)
