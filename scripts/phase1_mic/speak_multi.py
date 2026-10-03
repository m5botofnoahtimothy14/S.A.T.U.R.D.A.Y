import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
for i in (3, 2, 1):
    print(f"Get ready... {i}", flush=True)
    time.sleep(1.0)
for dev in (9, 1, 5):
    print(f"*** SPEAK LOUDLY for 4s -> device {dev} ***", flush=True)
    out = {}
    ears._record_native(dev, 4.0, out)
    if "samples" not in out:
        print(f"dev {dev}: FAIL {out.get('error')}", flush=True)
        continue
    s16 = ears._resample_to_16k(out["samples"], out["recorded_sr"])
    import numpy as np
    peak = int(abs(s16).max()); rms = float((np.abs(s16.astype(np.float64)**2).mean())**0.5)
    print(f"dev {dev}: sr={out['recorded_sr']} peak={peak} rms={rms:.1f}", flush=True)
    ears.save_wav(s16, 16000, f"D:\\speak_dev{dev}.wav")
    print(f"saved D:\\speak_dev{dev}.wav", flush=True)
print("DONE", flush=True)
