import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
secs = 8.0
for i in (3, 2, 1):
    print(f"Recording starts in {i}...", flush=True)
    time.sleep(1.0)
print(f"*** SPEAK NOW for {secs:.0f}s ***", flush=True)
res = ears.hear_once(secs)
print("HEARD_SOMETHING:", res.get("heard_something"), "| rms:", res.get("rms"),
      "| peak:", res.get("peak", "?"), "| device:", res.get("device"), flush=True)
print("TRANSCRIPT:", repr(res.get("text", "")), flush=True)
print("NOTE:", res.get("note", res.get("error", "ok")), flush=True)
