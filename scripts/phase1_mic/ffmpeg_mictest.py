import sys, time, subprocess
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
for i in (3, 2, 1):
    print(f"Get ready... {i}", flush=True)
    time.sleep(1.0)
print("*** SPEAK LOUDLY NOW (4s ffmpeg dshow) ***", flush=True)
r = subprocess.run(["ffmpeg", "-y", "-f", "dshow", "-i",
                    'audio=Microphone Array (Realtek(R) Audio)',
                    "-t", "4", "-ac", "1", "-ar", "16000",
                    r"D:\ffmpeg_mic.wav"],
                   capture_output=True, text=True, timeout=60)
print("RC:", r.returncode, flush=True)
print("STDERR tail:", r.stderr[-500:], flush=True)
from saturday import ears
import wave
with wave.open(r"D:\ffmpeg_mic.wav", "rb") as wf:
    n = wf.getnframes()
    raw = wf.readframes(n)
import numpy as np
s = np.frombuffer(raw, dtype=np.int16)
peak = int(abs(s).max()); rms = float((np.abs(s.astype(np.float64)**2).mean())**0.5)
print(f"FFMPEG WAV: peak={peak} rms={rms:.1f} n={len(s)}", flush=True)
