"""Voice chain proofs: Kokoro render smoke + denoise SNR gain. No mic needed."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_kokoro_render():
    from saturday import kokoro_voice as kv
    assert kv.available(), "kokoro_onnx import failed"
    v = kv.voices()
    assert len(v) >= 5, v
    out = str(Path(tempfile.mkdtemp(prefix="kokoro_test_")) / "t.wav")
    p = kv.render_wav("Saturday voice check.", path=out, voice="af_sarah")
    assert Path(p).exists() and Path(p).stat().st_size > 10000, p
    import soundfile as sf
    data, sr = sf.read(p)
    assert sr == 24000 and len(data) > sr // 2, (sr, len(data))


def test_denoise_gain():
    import numpy as np
    from saturday import ears
    sr = 16000
    t = np.arange(sr * 2) / sr
    speech = (np.sin(2 * np.pi * 220 * t)
              * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t)) * 9000).astype(np.float32)
    hum = (np.sin(2 * np.pi * 50 * t) * 2500
           + np.random.default_rng(7).normal(0, 1800, len(t))).astype(np.float32)
    noisy = np.clip(speech + hum, -32768, 32767).astype(np.int16)
    r = ears.denoise(noisy, sr)
    assert r["success"], r.get("error")
    assert r["snr_after"] >= r["snr_before"], r
    assert r["samples"].dtype == np.int16 and len(r["samples"]) == len(noisy)


def test_voice_chain_order():
    import inspect
    from interface import voice as v
    src = inspect.getsource(v.SATURDAYVoice.speak)
    ik = src.index("kokoro_voice")
    ip = src.index("piper_bin")
    iw = src.index("_windows_speak")
    if_ = src.index("_fallback_voice")
    assert ik < ip < iw < if_, "chain must be Kokoro → Piper → SAPI → pyttsx3"


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("VOICE GREEN")
