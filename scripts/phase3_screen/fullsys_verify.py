import sys, glob, os
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
print("STT_MODEL default:", ears.STT_MODEL, flush=True)
w = sorted(glob.glob(r"D:\SATURDAY_TEMP\saturday_hear_*.wav"), key=os.path.getmtime)[-1]
r = ears.transcribe(wav_path=w, language="en")
print("BASE:", repr(r.get("text")), "lang:", r.get("language"), flush=True)

from saturday import screen_operator as so
op = so.ScreenOperator()
before = op.screenshot(r"D:\vol_before.png")
v = op.volume("up", confirm=True)
print("VOLUME:", v, flush=True)
import time; time.sleep(1.0)
after = op.screenshot(r"D:\vol_after.png")
pc = op.pixel_change(before["path"], after["path"])
print("OSD changed_ratio:", round(pc.get("changed_ratio", -1), 4), flush=True)
m = op.media("playpause", confirm=True)
print("MEDIA:", m, flush=True)

from saturday import verse
print(verse.verse_of_day(), flush=True)
print(verse.verse_lookup("23:1"), flush=True)
print(verse.verse_lookup("xyz"), flush=True)
print("DONE", flush=True)
