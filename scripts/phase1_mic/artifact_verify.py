import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
ears.MIC_DEVICE = "12"  # force the junk device
cap = ears.capture(2.0)
print("forced-12 lands on device:", cap.get("device"), "rms:", cap.get("rms"), flush=True)
ears.MIC_DEVICE = ""
cap = ears.capture(2.0)
print("auto lands on device:", cap.get("device"), "rms:", cap.get("rms"), flush=True)
