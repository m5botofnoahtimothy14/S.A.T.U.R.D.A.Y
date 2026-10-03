import faulthandler
faulthandler.dump_traceback_later(50, exit=True)
print("import ears...", flush=True)
import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
print("ears imported", flush=True)
print("MIC:", ears.mic_available(), "STT:", ears.stt_available(), flush=True)
print("candidates...", flush=True)
c = ears._candidate_inputs()
print(f"candidates={c}", flush=True)
