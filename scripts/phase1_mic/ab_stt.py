"""A/B: tiny vs base faster-whisper on the USER'S OWN saved turns.
No new downloads: base (141MB) is already cached on D:.
Prints side-by-side so accuracy difference is visible, not claimed."""
import sys, glob, os
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
os.environ["HF_HUB_OFFLINE"] = "1"
from faster_whisper import WhisperModel

wavs = sorted(glob.glob(r"D:\SATURDAY_TEMP\saturday_hear_*.wav"),
              key=os.path.getmtime)[-8:]
print(f"{len(wavs)} turn WAVs", flush=True)
for name in ("tiny", "base"):
    print(f"loading {name}...", flush=True)
    m = WhisperModel(name, device="cpu", compute_type="int8")
    for w in wavs:
        segs, info = m.transcribe(w, beam_size=5, vad_filter=True)
        txt = " ".join(s.text.strip() for s in segs).strip()
        if not txt:  # same VAD fallback SATURDAY uses
            segs, info = m.transcribe(w, beam_size=5, vad_filter=False)
            txt = " ".join(s.text.strip() for s in segs).strip() + " [vad-off]"
        print(f"[{name}] {os.path.basename(w)} lang={info.language} :: {txt!r}", flush=True)
    del m
print("DONE", flush=True)
