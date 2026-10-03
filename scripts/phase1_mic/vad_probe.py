import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
import onnxruntime as ort, numpy as np
s = ort.InferenceSession(r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM\models\silero_vad.onnx",
                         providers=["CPUExecutionProvider"])
print("inputs:", [(i.name, i.shape) for i in s.get_inputs()], flush=True)
print("outputs:", [(o.name, o.shape) for o in s.get_outputs()], flush=True)
# 1s of silence -> all probs ~0 ?
state = np.zeros((2, 1, 128), dtype=np.float32)
sr = np.array([16000], dtype=np.int64)
probs = []
x = np.zeros(512, dtype=np.float32)
for _ in range(31):
    out, state = s.run(None, {"input": x.reshape(1, -1), "state": state, "sr": sr})
    probs.append(float(out[0][0]))
print(f"silence: max={max(probs):.3f} mean={sum(probs)/len(probs):.3f}", flush=True)
