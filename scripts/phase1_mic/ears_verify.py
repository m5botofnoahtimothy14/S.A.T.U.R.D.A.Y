import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
import logging
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
from saturday import ears
print("HF_HOME:", __import__("os").environ.get("HF_HOME"), flush=True)
print("STT_MODEL:", ears.STT_MODEL, flush=True)
m = ears.list_mics()
print("LIST OK:", m["success"], "n=", len(m["mics"]), flush=True)
for d in m["mics"]:
    print(f"  {d['index']}: {d['name']!r} api={d['host_api']} in={d['max_input_channels']} sr={d['default_samplerate']}", flush=True)
print("RESOLVE auto ->", ears.resolve_mic_device(), flush=True)
import os
os.environ["SATURDAY_MIC_DEVICE"] = "wasapi"
# reload MIC_DEVICE binding
ears.MIC_DEVICE = "wasapi"
print("RESOLVE 'wasapi' ->", ears.resolve_mic_device(), flush=True)
ears.MIC_DEVICE = ""
cap = ears.capture(2.0)
info = {k: v for k, v in cap.items() if k != "samples"}
print("CAPTURE:", info, flush=True)
print("HEARD:", ears.heard(cap["samples"]) if cap.get("success") else "n/a", flush=True)
