import glob
import os

from kokoro_onnx import Kokoro

SNAP = glob.glob(r"D:\S.A.T.U.R.D.A.Y\models\hf-hub\models--onnx-community--Kokoro-82M-v1.0-ONNX\snapshots\*")[0]
MODEL = os.path.join(SNAP, "onnx", "model.onnx")
VOICES = r"D:\S.A.T.U.R.D.A.Y\models\kokoro-voices.bin"

k = Kokoro(MODEL, VOICES)
print("voices:", k.get_voices()[:10])
samples, sr = k.create(
    "Saturday online. All systems nominal.", voice="af_sarah", speed=1.0, lang="en-us"
)
print("RENDER OK:", len(samples), "samples @", sr, "=", round(len(samples) / sr, 1), "sec audio")
import soundfile as sf

sf.write(r"D:\SATURDAY_TEMP\kokoro_test.wav", samples, sr)
print("saved kokoro_test.wav")
