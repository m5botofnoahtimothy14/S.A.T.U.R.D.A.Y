import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from unittest.mock import MagicMock
from saturday.selfheal import SelfHeal
core, sess = MagicMock(), MagicMock()
sess.camera.running = True
sess.camera.frames_captured = 1
h = SelfHeal(core, sess)
for c in h.run_checks():
    if c["name"] in ("ollama",):
        print(f"ollama: ok={c['ok']} healed={c.get('healed')} :: {c.get('detail')}", flush=True)
print("DONE", flush=True)
