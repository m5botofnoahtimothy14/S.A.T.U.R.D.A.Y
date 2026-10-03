import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
import numpy as np
for dev in (12, 9):
    out = {}
    ears._record_native(dev, 3.0, out)
    s = out["samples"].astype(np.float64)
    print(f"dev {dev} sr={out.get('recorded_sr')}: max={s.max():.0f} min={s.min():.0f} "
          f"mean={s.mean():.1f} rms={(np.abs(s**2).mean())**0.5:.1f} "
          f"clip%={100*(np.abs(s) > 32000).mean():.2f} "
          f"zeros%={100*(s == 0).mean():.1f}", flush=True)
import json
cfg = json.load(open(r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM\config\settings.json"))
print("settings mic_device:", cfg.get("audio", {}).get("mic_device"), flush=True)
