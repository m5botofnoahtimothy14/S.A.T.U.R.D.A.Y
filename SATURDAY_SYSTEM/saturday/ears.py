"""SATURDAY Ears — real local hearing. Mic + offline speech-to-text.

- capture()   : record N seconds from the default mic (16kHz mono).
- heard()     : energy gate — silence honestly reported, never hallucinated.
- transcribe(): faster-whisper (local CPU/int8, tiny model) → text.
- hear_once() : capture → gate → transcribe, one call.
- list_mics() : available input devices.

Fully offline after the first model download (~75MB tiny). No cloud STT,
no keys, audio never leaves the PC. Failures return
{"success": False, "error": ...} — silence returns success with text "".
"""

import logging
import os
import tempfile
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Ears")

try:
    import sounddevice as sd
    import numpy as np

    _MIC_AVAILABLE = True
    _MIC_ERROR = ""
except Exception as e:  # pragma: no cover
    sd = None
    np = None
    _MIC_AVAILABLE = False
    _MIC_ERROR = str(e)

try:
    from faster_whisper import WhisperModel

    _STT_AVAILABLE = True
    _STT_ERROR = ""
except Exception as e:  # pragma: no cover
    WhisperModel = None
    _STT_AVAILABLE = False
    _STT_ERROR = str(e)

STT_MODEL = os.getenv("SATURDAY_STT_MODEL", "tiny")
_stt_model = None


def mic_available() -> bool:
    return _MIC_AVAILABLE


def stt_available() -> bool:
    return _STT_AVAILABLE


def list_mics() -> Dict[str, Any]:
    if not _MIC_AVAILABLE:
        return {"success": False, "error": f"mic backend missing ({_MIC_ERROR})"}
    try:
        devices = sd.query_devices()
        inputs = [{"index": i, "name": d["name"],
                   "channels": d["max_input_channels"]}
                  for i, d in enumerate(devices) if d["max_input_channels"] > 0]
        default = sd.default.device
        return {"success": True, "mics": inputs, "default": default}
    except Exception as e:
        return {"success": False, "error": str(e)}


def capture(seconds: float = 5.0, samplerate: int = 16000) -> Dict[str, Any]:
    """Record mono int16 audio. Returns samples + level stats."""
    if not _MIC_AVAILABLE:
        return {"success": False, "error": f"mic backend missing ({_MIC_ERROR})"}
    seconds = min(max(float(seconds or 5.0), 1.0), 30.0)
    try:
        rec = sd.rec(int(seconds * samplerate), samplerate=samplerate,
                     channels=1, dtype="int16")
        sd.wait()
        samples = rec.flatten()
        peak = int(abs(samples).max()) if len(samples) else 0
        rms = float((np.abs(samples.astype(np.float64) ** 2).mean()) ** 0.5)
        return {"success": True, "samples": samples, "samplerate": samplerate,
                "seconds": seconds, "peak": peak, "rms": round(rms, 1)}
    except Exception as e:
        logger.warning(f"mic capture failed: {e}")
        return {"success": False, "error": str(e)}


def heard(samples, silence_rms: float = 60.0) -> bool:
    """Energy gate: was anything actually said?"""
    try:
        import numpy as _np

        rms = float((_np.abs(_np.asarray(samples).astype(_np.float64) ** 2).mean()) ** 0.5)
        return rms >= silence_rms
    except Exception:
        return False


def save_wav(samples, samplerate: int = 16000, path: Optional[str] = None) -> str:
    if path is None:
        path = str(Path(tempfile.gettempdir()) / f"saturday_hear_{int(time.time())}.wav")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(np.asarray(samples, dtype=np.int16).tobytes())
    return path


def _get_model():
    global _stt_model
    if _stt_model is None:
        _stt_model = WhisperModel(STT_MODEL, device="cpu", compute_type="int8")
    return _stt_model


def transcribe(samples=None, wav_path: Optional[str] = None,
               samplerate: int = 16000) -> Dict[str, Any]:
    """Speech → text, local whisper. Empty speech → text '' (not an error)."""
    if not _STT_AVAILABLE:
        return {"success": False, "error": f"faster-whisper missing ({_STT_ERROR})"}
    try:
        if wav_path is None:
            if samples is None:
                return {"success": False, "error": "Nothing to transcribe."}
            wav_path = save_wav(samples, samplerate)
        model = _get_model()
        segments, info = model.transcribe(wav_path, beam_size=5)
        text = " ".join(s.text.strip() for s in segments).strip()
        return {"success": True, "text": text,
                "language": getattr(info, "language", "?"),
                "heard_something": bool(text)}
    except Exception as e:
        logger.warning(f"transcription failed: {e}")
        return {"success": False, "error": str(e)}


def hear_once(seconds: float = 5.0) -> Dict[str, Any]:
    """One full hearing cycle: listen → gate → transcribe."""
    cap = capture(seconds)
    if not cap.get("success"):
        return cap
    if not heard(cap["samples"]):
        return {"success": True, "text": "", "heard_something": False,
                "note": f"Silence (rms {cap['rms']}). Nothing said."}
    res = transcribe(samples=cap["samples"], samplerate=cap["samplerate"])
    res["rms"] = cap["rms"]
    return res
