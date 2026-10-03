"""MIC LOCK-IN: find the device that hears YOU, plug it into SATURDAY.

Step 1 (calibrate): for each Realtek input, you get 4s to say
  "testing one two three". Ranks by level, writes the winner into
  SATURDAY_SYSTEM/config/settings.json [audio].mic_device so SATURDAY
  uses it automatically from now on.

Step 2 (session): `python mic_lockin.py --loop` listens in 6s turns and
  prints transcripts until Ctrl+C. Paste the session back to lock in.

Usage (run YOURSELF in PowerShell):
  python "D:\\S.A.T.U.R.D.A.Y\\scripts\\phase1_mic\\mic_lockin.py"
  python "D:\\S.A.T.U.R.D.A.Y\\scripts\\phase1_mic\\mic_lockin.py" --loop
"""
import json
import sys
import time

sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears

SETTINGS = r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM\config\settings.json"


def calibrate():
    info = ears.list_mics()
    if not info.get("success"):
        print("MIC BACKEND MISSING:", info.get("error"), flush=True)
        return
    cands = [d for d in info["mics"] if "realtek" in d["name"].lower()
             or "microphone array" in d["name"].lower()]
    print(f"Testing {len(cands)} Realtek candidates. Speak ONLY during YOUR 4s window.", flush=True)
    results = []
    for d in cands:
        dev = d["index"]
        print(f"\n>>> Device {dev} [{d['host_api']}] {d['name']} <<<", flush=True)
        print("    ...get ready...", flush=True)
        time.sleep(2.0)
        print('    *** SAY "testing one two three" NOW (4s) ***', flush=True)
        out: dict = {}
        ears._record_native(dev, 4.0, out)
        if "samples" not in out:
            print(f"    FAIL: {out.get('error')}", flush=True)
            continue
        s16 = ears._resample_to_16k(out["samples"], out.get("recorded_sr", 16000))
        import numpy as np
        f = s16.astype(np.float64)
        peak = int(abs(s16).max())
        rms = float((np.abs(f ** 2).mean()) ** 0.5)
        dc = float(f.mean())
        zeros = float((f == 0).mean())
        junk = abs(dc) > 400.0 or zeros > 0.40
        wav = ears.save_wav(s16, 16000, f"D:\\SATURDAY_TEMP\\lockin_dev{dev}.wav")
        print(f"    dev={dev} sr={out.get('recorded_sr')} peak={peak} rms={rms:.1f} "
              f"dc={dc:.0f} zeros={zeros:.0%} wav={wav}"
              f"{'  <-- JUNK (driver artifact, excluded)' if junk else ''}", flush=True)
        if junk:
            continue
        results.append((rms, peak, dev, out.get("recorded_sr")))
    if not results:
        print("\nNO device produced audio. Mic is blocked below app level.", flush=True)
        return
    results.sort(reverse=True)
    rms, peak, dev, sr = results[0]
    print(f"\n=== LOCKIN: device {dev} wins (rms {rms:.1f}, peak {peak}, native {sr}Hz) ===", flush=True)
    if rms < 120.0:
        print("WARNING: even the best is quiet — speak louder / move closer / check boost.", flush=True)
    try:
        with open(SETTINGS, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        cfg.setdefault("audio", {})["mic_device"] = str(dev)
        with open(SETTINGS, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=4)
        print(f"PLUGGED IN: settings.json [audio].mic_device = \"{dev}\"", flush=True)
    except Exception as e:
        print(f"Could NOT write settings ({e}). Set env instead: setx SATURDAY_MIC_DEVICE {dev}", flush=True)
    print(f"LOCKIN device={dev} rms={rms:.1f} peak={peak}  <-- paste this back", flush=True)


def loop():
    print("SATURDAY listen session. Speak in each 6s turn. Ctrl+C to end.", flush=True)
    n = 0
    try:
        while True:
            n += 1
            print(f"\n--- turn {n}: SPEAK NOW (6s) ---", flush=True)
            res = ears.hear_once(6.0)
            print(f"heard={res.get('heard_something')} rms={res.get('rms')} "
                  f"device={res.get('device')}", flush=True)
            print(f"TRANSCRIPT: {res.get('text', '')!r}", flush=True)
            if not res.get("success"):
                print("ERROR:", res.get("error"), flush=True)
    except KeyboardInterrupt:
        print(f"\nSession ended after {n} turns.", flush=True)


if __name__ == "__main__":
    if "--loop" in sys.argv:
        loop()
    else:
        calibrate()
