import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
import re, time
env = dict(re.findall(r"^([A-Za-z_]+)=(.*)$",
                      open(r"D:\S.A.T.U.R.D.A.Y\.env", encoding="utf-8").read(),
                      re.M))
url = env.get("databaseURL", "").strip().strip('"').strip("'")
print("databaseURL present:", bool(url),
      "| host:", url.split("//")[-1].split("/")[0] if url else None, flush=True)
sa = r"D:\S.A.T.U.R.D.A.Y\aegis-os-75256-firebase-adminsdk-fbsvc-a2ec5386e4.json"
from realtime_bridge import RealtimeDatabaseBridge
b = RealtimeDatabaseBridge(service_account=sa, database_url=url, node_id="saturday-node")
print("bridge constructed", flush=True)
b.start(lambda: {"online": True, "probe": "firebase-link-test"},
        lambda cmd, meta: {"refused-in-test": True})
time.sleep(6.0)
st = b.status() if hasattr(b, "status") else {}
print("bridge status:", {k: (v if k != "url" else "...") for k, v in (st.items() if isinstance(st, dict) else [])}, flush=True)
try:
    b.stop()
    print("bridge stopped clean", flush=True)
except Exception as e:
    print("stop note:", str(e)[:100], flush=True)
print("DONE", flush=True)
