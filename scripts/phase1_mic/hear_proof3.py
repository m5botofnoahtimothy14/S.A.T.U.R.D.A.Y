import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
secs = 30.0
print(f"RECORDING {secs:.0f}s - KEEP TALKING", flush=True)
res = ears.hear_once(secs)
print("HEARD_SOMETHING:", res.get("heard_something"), "| rms:", res.get("rms"),
      "| device:", res.get("device"), flush=True)
print("TRANSCRIPT:", repr(res.get("text", "")), flush=True)
print("NOTE:", res.get("note", res.get("error", "ok")), flush=True)
