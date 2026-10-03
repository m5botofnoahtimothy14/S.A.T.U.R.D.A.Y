import sys, glob, os
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
print("resolve:", {k: ears.resolve_language(k) for k in
                   ["auto", "", "en", "en-US", "en-GB", "en-IN", "tamil", "TA", "french", "fr-FR", "xx"]}, flush=True)
wavs = sorted(glob.glob(r"D:\SATURDAY_TEMP\saturday_hear_*.wav"),
              key=os.path.getmtime)[-4:]
for w in wavs:
    a = ears.transcribe(wav_path=w)  # auto
    e = ears.transcribe(wav_path=w, language="en")  # forced english
    print(f"{os.path.basename(w)}:", flush=True)
    print(f"  auto lang={a.get('language')} text={a.get('text')!r}", flush=True)
    print(f"  en   lang={e.get('language')} text={e.get('text')!r}", flush=True)
