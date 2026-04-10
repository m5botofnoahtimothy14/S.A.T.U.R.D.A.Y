import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

# Keep parity with verify_aegis.py path setup so optional packages are discoverable.
for extra in (
    os.path.join(ROOT, "pip_packages"),
    "F:/aegis_packages",
):
    if os.path.isdir(extra):
        sys.path.insert(0, extra)

from core.audio_service import CrossPlatformAudio  # noqa: E402
from core.sound_monitor import SoundMonitor  # noqa: E402
from core.event_bus import EventBus  # noqa: E402

try:
    import speech_recognition as sr
except ImportError:
    sr = None


def main():
    print("=" * 72)
    print("AEGIS Mic + Voice Pipeline Diagnostic")
    print("=" * 72)

    audio = CrossPlatformAudio()
    mics = audio.list_microphones()
    print(f"[1] Microphones detected: {len(mics)}")
    for idx, name in mics[:10]:
        print(f"    - [{idx}] {name}")

    supported = [
        "noise",
        "person_speaking",
        "people_speaking",
        "tv",
        "hall",
        "tv_channel",
        "small_kids",
    ]
    print("\n[2] Supported acoustic scene labels:")
    print("    " + ", ".join(supported))

    if sr is None or audio.recognizer is None or audio.mic is None:
        print("\n[3] SpeechRecognition backend not available.")
        return 1

    print("\n[3] Capturing a live sample (speak now or make surrounding noise)...")
    raw_audio = None
    with audio.mic as source:
        audio.recognizer.adjust_for_ambient_noise(source, duration=0.8)
        try:
            raw_audio = audio.recognizer.listen(source, timeout=8, phrase_time_limit=6)
        except sr.WaitTimeoutError:
            print("    Timeout: no audio phrase detected.")
            return 1

    raw_bytes = raw_audio.get_raw_data()
    pcm = np.frombuffer(raw_bytes, dtype=np.int16) if raw_bytes else np.zeros(0, dtype=np.int16)
    rms = int(np.sqrt(np.mean(np.square(pcm.astype(np.float64))))) if pcm.size else 0
    peak = int(np.max(np.abs(pcm))) if pcm.size else 0
    print(f"    Captured bytes: {len(raw_bytes)}")
    print(f"    Signal RMS: {rms}")
    print(f"    Signal PEAK: {peak}")

    if not raw_bytes or peak < 120:
        print("    Mic capture appears too weak for reliable recognition.")
        return 1

    sample_np = audio._audio_to_float32(raw_audio)
    monitor = SoundMonitor(EventBus())
    level_dbfs = monitor._rms_db(sample_np)
    level_db = level_dbfs + 100.0
    dom_freq, _, mag = monitor._dominant_freq(sample_np, audio.sample_rate)
    centroid = monitor._spectral_centroid(mag, audio.sample_rate)
    bandwidth = monitor._spectral_bandwidth(mag, audio.sample_rate, centroid)
    crest = (np.max(np.abs(mag)) + 1e-6) / (np.mean(np.abs(mag)) + 1e-6)
    scene, conf, scores = monitor._infer_scene(
        level_db=level_db,
        dom_freq=dom_freq,
        mag=mag,
        samples=sample_np,
        sr=audio.sample_rate,
        centroid=centroid,
        bandwidth=bandwidth,
        crest=crest,
    )
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    print("\n[4] Acoustic scene inference from captured sample:")
    print(f"    Loudness: {level_db:.1f} dB (normalized), {level_dbfs:.1f} dBFS")
    print(f"    Primary label: {scene} ({conf:.2%})")
    print(f"    Top candidates: {', '.join([f'{k}:{v:.2f}' for k, v in ranked[:4]])}")

    text = audio.recognize_speech(raw_audio)
    print("\n[5] Speech pipeline output:")
    print(f"    Recognized text: {text or '<none>'}")

    if audio.last_speaker_result:
        print("\n[6] Speaker verification result:")
        print(f"    {audio.last_speaker_result}")
    else:
        print("\n[6] Speaker verification result: no enrolled voice profile found.")

    ok = bool(text or scene)
    print("\n" + "=" * 72)
    print("RESULT:", "PASS" if ok else "WARN")
    print("=" * 72)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
