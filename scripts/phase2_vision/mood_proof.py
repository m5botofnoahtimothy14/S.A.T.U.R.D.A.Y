import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
import cv2
from saturday import senses
cap, backend, idx = senses.open_camera()
frames = []
t0 = time.time()
while time.time() - t0 < 6.0:
    ok, f = cap.read()
    if ok and f is not None:
        frames.append(f)
cap.release()
print(f"n={len(frames)} ({len(frames)/(time.time()-t0):.1f} fps)", flush=True)
senses.mood_reset()
for i, f in enumerate(frames[:: max(1, len(frames)//5)][:5]):
    senses._mood_last_run = 0
    fd = senses.find_faces(f)
    m = senses.mood_live(f)
    print(f"f{i}: faces={fd.get('count')} boxes={fd.get('boxes')} "
          f"MOOD={m.get('mood')} conf={m.get('confidence')} stab={m.get('stability')} "
          f"votes={m.get('votes')} err={m.get('error')}", flush=True)
    if m.get("success") and i == 2:
        b = m["face"]
        ann = f.copy()
        cv2.rectangle(ann, (b["x"], b["y"]), (b["x"]+b["w"], b["y"]+b["h"]), (0, 255, 0), 3)
        cv2.putText(ann, f"{m['mood']} {m['confidence']:.0%}", (b["x"], max(0, b["y"]-10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        cv2.imwrite(r"D:\mood_proof.jpg", ann)
        print("saved D:\\mood_proof.jpg", flush=True)
print("DONE", flush=True)
