import sys, wave
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
import numpy as np, onnxruntime as ort
with wave.open(r"D:\SATURDAY_TEMP\saturday_hear_1791043194.wav", "rb") as wf:
    s = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
print(f"rms={(np.abs(s.astype(np.float64)**2).mean())**0.5:.0f} max={abs(s).max()}", flush=True)
sess = ort.InferenceSession(r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM\models\silero_vad.onnx",
                            providers=["CPUExecutionProvider"])
x = (s.astype(np.float32) / 32768.0)[: (len(s)//512)*512]
state = np.zeros((2, 1, 128), dtype=np.float32)
sr = np.array(16000, dtype=np.int64)  # scalar, not [16000]
probs = []
for i in range(0, len(x), 512):
    out, state = sess.run(None, {"input": x[i:i+512].reshape(1, -1), "state": state, "sr": sr})
    probs.append(float(out[0][0]))
probs = np.array(probs)
print(f"scalar-sr: max={probs.max():.3f} mean={probs.mean():.3f} "
      f"frac>0.5={(probs>0.5).mean():.3f} frac>0.3={(probs>0.3).mean():.3f}", flush=True)
print("top5 chunk idx:", np.argsort(probs)[-5:], flush=True)
