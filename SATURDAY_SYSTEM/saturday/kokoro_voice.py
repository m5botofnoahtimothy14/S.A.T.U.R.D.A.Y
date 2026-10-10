"""SATURDAY Kokoro voice — human-like local TTS (Kokoro-82M ONNX, CPU).

Proven on this box: fp32 session loads, 10 voices render at 24kHz.
NOT the q8f16 quant — it access-violates this ONNX Runtime build, so the
loader refuses it loudly instead of crashing the process.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Kokoro")

MODEL_DIR = Path(os.getenv("SATURDAY_KOKORO_DIR",
                           r"D:\S.A.T.U.R.D.A.Y\models\hf-hub\models--onnx-community--Kokoro-82M-v1.0-ONNX\snapshots\1939ad2a8e416c0acfeecc08a694d14ef25f2231\onnx"))
VOICES_PATH = Path(os.getenv("SATURDAY_KOKORO_VOICES",
                             r"D:\S.A.T.U.R.D.A.Y\models\kokoro-voices.bin"))
MODEL_FILE = os.getenv("SATURDAY_KOKORO_MODEL", "model.onnx")  # fp32: proven stable here

_kokoro = None
_kokoro_error = ""


def available() -> bool:
    try:
        import kokoro_onnx  # noqa
        return True
    except Exception as e:
        return False


def _get():
    global _kokoro, _kokoro_error
    if _kokoro is not None:
        return _kokoro
    from kokoro_onnx import Kokoro

    model_path = MODEL_DIR / MODEL_FILE
    if "q8" in MODEL_FILE.lower() or "q4" in MODEL_FILE.lower():
        raise RuntimeError("quantized Kokoro models crash this ONNX Runtime build; using fp32 model.onnx")
    if not model_path.exists():
        raise RuntimeError(f"Kokoro model missing: {model_path}")
    if not VOICES_PATH.exists():
        raise RuntimeError(f"Kokoro voices missing: {VOICES_PATH}")
    _kokoro = Kokoro(str(model_path), str(VOICES_PATH))
    logger.info(f"Kokoro voice ready ({MODEL_FILE}, {len(_kokoro.get_voices())} voices).")
    return _kokoro


def voices() -> List[str]:
    try:
        return list(_get().get_voices())
    except Exception as e:
        logger.warning(f"Kokoro voices unavailable: {e}")
        return []


def render(text: str, voice: str = "af_sarah", speed: float = 1.0,
           lang: str = "en-us") -> Dict[str, Any]:
    """Text → (samples, 24000Hz). Raises with honest error on failure."""
    text = (text or "").strip()
    if not text:
        raise ValueError("empty text")
    t0 = time.time()
    k = _get()
    avail = k.get_voices()
    if voice not in avail:
        voice = "af_sarah" if "af_sarah" in avail else avail[0]
    samples, sr = k.create(text[:1000], voice=voice, speed=speed, lang=lang)
    return {"samples": samples, "sr": int(sr), "voice": voice,
            "seconds": round(time.time() - t0, 2)}


def render_wav(text: str, path: Optional[str] = None, **kw) -> str:
    """Render + write WAV file. Returns path."""
    import soundfile as sf

    res = render(text, **kw)
    if path is None:
        tmp = Path(os.getenv("SATURDAY_D_TMP", r"D:\SATURDAY_TEMP"))
        tmp.mkdir(parents=True, exist_ok=True)
        path = str(tmp / f"saturday_tts_{int(time.time())}.wav")
    sf.write(path, res["samples"], res["sr"])
    return path
