"""Just you + SATURDAY voice, no whole system.

Loop: listen 6s -> transcribe (whisper tiny, D: cached) -> SATURDAY speaks
a reply out loud (Windows voice). Say "goodbye" to end.

Usage (run YOURSELF in PowerShell):
  python "D:\\S.A.T.U.R.D.A.Y\\scripts\\phase1_mic\\voice_mini.py"
"""
import sys
import time

sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
from interface.voice import SATURDAYVoice

voice = SATURDAYVoice(core=None)


def main():
    print("SATURDAY mini voice. Speak each turn; say 'goodbye' to end. Ctrl+C quits.", flush=True)
    voice.speak("Voice check. I am listening.")
    n = 0
    try:
        while True:
            n += 1
            print(f"\n--- turn {n}: SPEAK NOW (6s) ---", flush=True)
            res = ears.hear_once(6.0)
            text = (res.get("text", "") or "").strip()
            print(f"YOU: {text!r} (rms {res.get('rms')}, device {res.get('device')})", flush=True)
            if not res.get("success"):
                print("HEAR ERROR:", res.get("error"), flush=True)
                continue
            if not text:
                line = "I didn't catch that. Say it again."
            elif "goodbye" in text.lower().replace(" ", ""):
                line = "Goodbye."
                print(f"SATURDAY: {line!r}", flush=True)
                voice.speak(line)
                break
            else:
                line = f"You said: {text}"
            print(f"SATURDAY: {line!r}", flush=True)
            voice.speak(line)
    except KeyboardInterrupt:
        print(f"\nEnded after {n} turns.", flush=True)


if __name__ == "__main__":
    main()
