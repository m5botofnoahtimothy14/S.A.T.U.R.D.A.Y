import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from interface.voice import SATURDAYVoice
v = SATURDAYVoice(core=None)
line = "Hi, I'm Edith. Tell me how I sound, smooth enough for you?"
for tag in ("kristin", "kathleen", "edith"):
    print(f"*** candidate: {tag} - LISTEN ***", flush=True)
    v.speak(line, voice=tag)
print("DONE - reply 1=kristin 2=kathleen 3=lessac(EDITH now)", flush=True)
