import faulthandler, sys, time
faulthandler.dump_traceback_later(45, exit=True)
print("t0 import sd", flush=True)
import sounddevice as sd
print("t1 sd ok", flush=True)
print("query...", flush=True)
devs = sd.query_devices()
print(f"t2 query ok n={len(devs)}", flush=True)
