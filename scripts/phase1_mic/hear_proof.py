"""Part 1 live proof: record N seconds via SATURDAY ears, transcribe, print.
Usage: python -u D:\\hear_proof.py [seconds]
Speak a test sentence when prompted."""
import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
print(f"=== SATURDAY hear-proof: speak NOW for {secs:.0f}s ===", flush=True)
res = ears.hear_once(secs)
print("HEARD_SOMETHING:", res.get("heard_something"), "| rms:", res.get("rms"),
      "| device:", res.get("device"), flush=True)
print("TRANSCRIPT:", repr(res.get("text", "")), flush=True)
if not res.get("success"):
    print("ERROR:", res.get("error"), flush=True)
print("NOTE:", res.get("note", res.get("error", "ok")), flush=True)
