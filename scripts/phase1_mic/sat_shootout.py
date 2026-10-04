import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from interface.voice import SATURDAYVoice
v = SATURDAYVoice(core=None)
line = "Saturday here... deep, smooth... and fully articulated. How do I sound, sir?"
for tag in ("joe", "john", "bryce"):
    print(f"*** candidate: {tag} - LISTEN ***", flush=True)
    v.speak(line, voice=tag)
print("DONE - reply 1=joe 2=john 3=bryce(current)", flush=True)
