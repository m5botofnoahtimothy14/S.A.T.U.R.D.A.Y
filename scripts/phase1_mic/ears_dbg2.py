import sys, threading
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
cands = ears._candidate_inputs()
print("cands:", cands, flush=True)
for device in cands[:3]:
    out = {}
    w = threading.Thread(target=ears._record_native, args=(device, 2.0, out), daemon=True)
    w.start()
    w.join(timeout=12.0)
    print(f"dev {device}: alive={w.is_alive()} keys={list(out)} err={out.get('error')}", flush=True)
    try:
        ears.sd.stop()
    except Exception as e:
        print("stop err", e, flush=True)
