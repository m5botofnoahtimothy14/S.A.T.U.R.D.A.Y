import importlib.util
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
for extra in (
    os.path.join(ROOT, "pip_packages"),
    "F:/saturday_packages",
):
    if os.path.isdir(extra):
        sys.path.insert(0, extra)

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from core.identity.voice_biometric import VoiceBiometricEngine  # noqa: E402
except Exception:
    module_path = os.path.join(ROOT, "core", "identity", "voice_biometric.py")
    spec = importlib.util.spec_from_file_location("voice_biometric", module_path)
    if spec is None or spec.loader is None:
        raise
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    VoiceBiometricEngine = module.VoiceBiometricEngine


def rms_db(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(samples * samples)))
    if rms <= 1e-12:
        return -120.0
    return float(20.0 * np.log10(rms + 1e-12))


def to_samples(audio_data, sample_rate: int = 16000) -> np.ndarray:
    raw = audio_data.get_raw_data(convert_rate=sample_rate, convert_width=2)
    if not raw:
        return np.zeros(0, dtype=np.float32)
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return np.clip(arr, -1.0, 1.0)


def clamp(v: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, v)))


def main():
    print("=" * 72)
    print("SATURDAY Audio Threshold Calibration")
    print("=" * 72)

    if sr is None:
        print("SpeechRecognition package is not available.")
        return 1

    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    with mic as source:
        print("\n[1/3] Measuring ambient noise for 4 seconds...")
        recognizer.adjust_for_ambient_noise(source, duration=1.0)
        ambient_audio = recognizer.record(source, duration=4.0)

        print("[2/3] Speak in your normal voice for up to 6 seconds...")
        try:
            speech_audio = recognizer.listen(source, timeout=8.0, phrase_time_limit=6.0)
        except sr.WaitTimeoutError:
            print("No speech phrase detected. Capturing fallback window for 4 seconds.")
            speech_audio = recognizer.record(source, duration=4.0)

    ambient = to_samples(ambient_audio)
    speech = to_samples(speech_audio)
    ambient_dbfs = rms_db(ambient)
    speech_dbfs = rms_db(speech)
    ambient_db = ambient_dbfs + 100.0
    speech_db = speech_dbfs + 100.0
    snr = speech_db - ambient_db

    # Higher SNR can use a lower offset; low SNR needs stricter gating.
    if snr >= 10.0:
        base_offset = 6.0
    elif snr >= 6.0:
        base_offset = 8.0
    else:
        base_offset = 10.0
    sound_threshold_db = clamp(ambient_db + base_offset, 45.0, 80.0)

    engine = VoiceBiometricEngine(db_path=os.path.join(ROOT, "data", "voice_profiles.json"))
    voice_threshold = 0.72
    score_speech = None
    score_ambient = None
    profile_scope = "admin"

    if engine.has_profiles(admin_only=True):
        speech_match = engine.verify_speaker(speech, 16000, threshold=0.0, admin_only=True)
        ambient_match = engine.verify_speaker(ambient, 16000, threshold=0.0, admin_only=True)
        score_speech = float(speech_match.get("score", -1.0))
        score_ambient = float(ambient_match.get("score", -1.0))
    elif engine.has_profiles(admin_only=False):
        profile_scope = "any"
        speech_match = engine.verify_speaker(speech, 16000, threshold=0.0, admin_only=False)
        ambient_match = engine.verify_speaker(ambient, 16000, threshold=0.0, admin_only=False)
        score_speech = float(speech_match.get("score", -1.0))
        score_ambient = float(ambient_match.get("score", -1.0))
    else:
        print("No enrolled voice profiles found. Keeping default biometric threshold.")

    if score_speech is not None and score_speech >= 0 and score_ambient is not None and score_ambient >= 0:
        margin = max(0.08, (score_speech - score_ambient) * 0.55)
        voice_threshold = clamp(score_ambient + margin, 0.62, 0.90)

    result = {
        "captured_at": time.time(),
        "ambient_db": round(ambient_db, 2),
        "ambient_dbfs": round(ambient_dbfs, 2),
        "speech_db": round(speech_db, 2),
        "speech_dbfs": round(speech_dbfs, 2),
        "snr_db": round(snr, 2),
        "sound_threshold_db": round(sound_threshold_db, 2),
        "voice_biometric_threshold": round(voice_threshold, 3),
        "speaker_scope": profile_scope,
        "speaker_score_speech": None if score_speech is None else round(score_speech, 4),
        "speaker_score_ambient": None if score_ambient is None else round(score_ambient, 4),
    }

    out_path = os.path.join(ROOT, "data", "audio_calibration.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("\n[3/3] Recommended thresholds")
    print(f"  SOUND_MONITOR_THRESHOLD_DB={result['sound_threshold_db']}")
    print(f"  VOICE_BIOMETRIC_THRESHOLD={result['voice_biometric_threshold']}")
    print(f"  Saved: {out_path}")
    print("\nRestart SATURDAY to apply calibration automatically.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
