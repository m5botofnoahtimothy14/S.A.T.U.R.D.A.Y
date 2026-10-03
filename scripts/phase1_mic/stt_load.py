import os
os.environ["HF_HOME"] = r"D:\S.A.T.U.R.D.A.Y\.huggingface"
os.environ["HF_HUB_OFFLINE"] = "1"
print("loading tiny...", flush=True)
from faster_whisper import WhisperModel
m = WhisperModel("tiny", device="cpu", compute_type="int8")
print("TINY LOADED OK", flush=True)
# transcribe silence WAV -> should be empty, proves pipeline incl. VAD
import wave, struct
p = r"D:\silence16k.wav"
with wave.open(p, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
    wf.writeframes(b"\x00" * 16000 * 2 * 2)
segs, info = m.transcribe(p, beam_size=5, vad_filter=True)
txt = " ".join(s.text.strip() for s in segs).strip()
print(f"SILENCE TEST text={txt!r} lang={info.language}", flush=True)
