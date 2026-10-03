"""Standalone mic test OUTSIDE saturnday - 5s record, WAV to D:, peak/RMS."""
import sounddevice as sd, numpy as np, wave, time, sys

candidates = [9, 1, 5, 12]  # WASAPI first, then MME, DS, WDM-KS
seconds = 5
for dev in candidates:
    print(f"\n=== trying device {dev} ===", flush=True)
    try:
        d = sd.query_devices(dev)
        print(f"name={d['name']!r} sr={d['default_samplerate']} in_ch={d['max_input_channels']}", flush=True)
    except Exception as e:
        print(f"query failed: {e}", flush=True)
        continue
    for sr in (16000, 48000):
        print(f"-- {seconds}s @ {sr}Hz mono int16 ... SPEAK NOW", flush=True)
        try:
            rec = sd.rec(int(seconds*sr), samplerate=sr, channels=1, dtype="int16", device=dev)
            sd.wait()
            s = rec.flatten()
            peak = int(abs(s).max())
            rms = float((np.abs(s.astype(np.float64)**2).mean())**0.5)
            print(f"RESULT dev={dev} sr={sr} peak={peak} rms={rms:.1f} max={s.max()} min={s.min()} mean={s.mean():.1f}", flush=True)
            path = f"D:\\mic_test_dev{dev}_{sr}.wav"
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
                wf.writeframes(s.astype(np.int16).tobytes())
            print(f"saved {path}", flush=True)
            if rms < 1.0:
                print("SILENT (rms<1) -> device-level or muted", flush=True)
            # only save one sr per device for brevity? keep both
        except Exception as e:
            print(f"RECORD FAILED dev={dev} sr={sr}: {e}", flush=True)
print("DONE")
