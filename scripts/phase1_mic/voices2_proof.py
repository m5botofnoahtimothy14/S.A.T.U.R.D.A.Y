import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from interface.voice import SATURDAYVoice
v = SATURDAYVoice(core=None)
print("*** EDITH (lessac) SPEAKING - listen ***", flush=True)
v.speak("Hi, I'm Edith. Same mind, new voice. How do I sound?", voice="edith")
print("*** SATURDAY (bryce) SPEAKING - listen ***", flush=True)
v.speak("Saturday here. Deep, cool, and ready. All systems running.")
print("DONE", flush=True)
