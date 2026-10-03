import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
import sounddevice as sd, numpy as np
for i in (3, 2, 1):
    print(f"Get ready... {i}", flush=True)
    time.sleep(1.0)
for dev in (9, 1):
    print(f"*** SPEAK LOUDLY 4s -> device {dev} STEREO ***", flush=True)
    try:
        rec = sd.rec(int(4.0 * 48000), samplerate=48000, channels=2, dtype="int16", device=dev)
        sd.wait()
        for ch in range(2):
            c = rec[:, ch]
            peak = int(abs(c).max()); rms = float((np.abs(c.astype(np.float64)**2).mean())**0.5)
            print(f"dev {dev} ch{ch}: peak={peak} rms={rms:.1f}", flush=True)
    except Exception as e:
        print(f"dev {dev}: FAIL {str(e)[:150]}", flush=True)
        # retry at 44100 for MME
        try:
            rec = sd.rec(int(4.0 * 44100), samplerate=44100, channels=2, dtype="int16", device=dev)
            sd.wait()
            for ch in range(2):
                c = rec[:, ch]
                peak = int(abs(c).max()); rms = float((np.abs(c.astype(np.float64)**2).mean())**0.5)
                print(f"dev {dev}@44100 ch{ch}: peak={peak} rms={rms:.1f}", flush=True)
        except Exception as e2:
            print(f"dev {dev}@44100: FAIL {str(e2)[:150]}", flush=True)
print("DONE", flush=True)
