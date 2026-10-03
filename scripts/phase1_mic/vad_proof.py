import sys, glob, os, wave
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
import numpy as np
from saturday import ears
wavs = sorted(glob.glob(r"D:\SATURDAY_TEMP\saturday_hear_*.wav"), key=os.path.getmtime)[-3:]
for w in wavs:
    with wave.open(w, "rb") as wf:
        s = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    nv = ears.neural_vad(s)
    print(f"{os.path.basename(w)}: avail={nv.get('available')} max={nv.get('max_prob')} "
          f"ratio={nv.get('speech_ratio')} trimmed_len={len(nv.get('trimmed', []))} orig={len(s)}", flush=True)
r = ears.transcribe(wav_path=wavs[-1], language="en")
print("TRIMMED TRANSCRIBE:", repr(r.get("text")), "trim:", r.get("vad_trim"), flush=True)
print("DONE", flush=True)
