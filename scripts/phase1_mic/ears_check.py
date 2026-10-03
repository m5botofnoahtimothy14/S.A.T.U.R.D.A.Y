import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
print("MIC_AVAIL:", ears.mic_available(), "STT_AVAIL:", ears.stt_available())
print("STT_MODEL:", ears.STT_MODEL, "GAIN:", ears.MIC_GAIN, "DEV:", repr(ears.MIC_DEVICE))
print("CANDIDATES:", ears._candidate_inputs())
print("LIST:", ears.list_mics())
cap = ears.capture(seconds=3)
info = {k: v for k, v in cap.items() if k != "samples"}
print("CAPTURE:", info)
if cap.get("success"):
    print("HEARD:", ears.heard(cap["samples"]), "rms gate=120")
