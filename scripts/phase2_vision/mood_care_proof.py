import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from unittest.mock import MagicMock
from saturday.mind import MindLoop
from saturday import humanvoice as hv

for m in ("angry", "sad", "anxious", "happy", "neutral"):
    print(f"{m}: {hv.mood_care_line(m, 'boss')[0][:90]}", flush=True)

core = MagicMock()
core.pmv.secure_search.return_value = []
core._hydration_entries.return_value = [{"ml": 3000, "at": 9999999999}]
said = []
core.session.inbox_add.side_effect = lambda **kw: said.append(kw) or "T1"
core.session.mood_context.return_value = "mood angry (85%, 2s ago)"
mind = MindLoop(core, observe_fn=lambda: {})
mind.episode = lambda t: print("EPISODE:", t, flush=True)
print("tick angry:", mind.tick({"present": "boss", "mood": "angry", "mood_confidence": 0.85}), flush=True)
print("said:", said[-1]["text"][:100] if said else None, flush=True)
print("agent ctx:", core.session.mood_context(), flush=True)
print("DONE", flush=True)
