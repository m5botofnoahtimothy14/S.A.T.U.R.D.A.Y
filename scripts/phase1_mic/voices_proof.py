import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from interface.voice import SATURDAYVoice
v = SATURDAYVoice(core=None)
t0 = time.time()
print("*** SATURDAY (ryan) SPEAKING ***", flush=True)
v.speak("SATURDAY online. Neural voice ready.")
print(f"saturday took {time.time()-t0:.1f}s", flush=True)
t0 = time.time()
print("*** EDITH (amy) SPEAKING ***", flush=True)
v.speak("EDITH here. Same mind, at your service.", voice="edith")
print(f"edith took {time.time()-t0:.1f}s", flush=True)
print("DONE", flush=True)
