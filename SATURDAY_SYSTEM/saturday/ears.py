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

STT_MODEL = os.getenv("SATURDAY_STT_MODEL", "base")
MIC_GAIN = float(os.getenv("SATURDAY_MIC_GAIN", "2.0") or 2.0)
MIC_DEVICE = os.getenv("SATURDAY_MIC_DEVICE", "").strip()
_stt_model = None


def _prefer_offline_stt():
    """If a whisper model is already cached, stay offline (frozen exes and
    flaky networks must not depend on hub roundtrips to hear)."""
    try:
        hub = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
        if not os.path.isdir(hub):
            return
        for entry in os.listdir(hub):
            if entry.startswith(("models--Systran--faster-whisper-",
                                 "models--openai--whisper-")):
                snap = os.path.join(hub, entry, "snapshots")
                if os.path.isdir(snap) and os.listdir(snap):
                    os.environ.setdefault("HF_HUB_OFFLINE", "1")
                    return
    except Exception:
        pass


_prefer_offline_stt()


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


def _candidate_inputs():
    """Real mics first (array/mic/realtek), virtual mappers last.
    SATURDAY_MIC_DEVICE pins one (locked in after live calibration)."""
    if MIC_DEVICE and MIC_DEVICE.lstrip("-").isdigit():
        return [int(MIC_DEVICE)]
    try:
        devices = sd.query_devices()
    except Exception:
        return []
    ranked, fallback = [], []
    for i, d in enumerate(devices):
        try:
            if d["max_input_channels"] <= 0:
                continue
        except Exception:
            continue
        name = str(d.get("name", "")).lower()
        if any(k in name for k in ("stereo mix", "mapper", "virtual", "capturer")):
            fallback.append(i)
            continue
        score = 0
        if "microphone array" in name:
            score += 3
        if "microphone" in name or " mic" in name or name.startswith("mic"):
            score += 2
        if "realtek" in name:
            score += 1
        ranked.append((-score, i))
    ranked.sort()
    return [i for _, i in ranked] + fallback


def _record_once(device, seconds: float, samplerate: int, out: dict):
    try:
        rec = sd.rec(int(seconds * samplerate), samplerate=samplerate,
                     channels=1, dtype="int16", device=device)
        sd.wait()
        out["samples"] = rec.flatten()
    except Exception as e:
        out["error"] = str(e)[:160]


def capture(seconds: float = 5.0, samplerate: int = 16000) -> Dict[str, Any]:
    """Record mono int16 audio. Tries real mics in order, watchdog-guarded
    (a dead default device can block forever — never hang the caller)."""
    if not _MIC_AVAILABLE:
        return {"success": False, "error": f"mic backend missing ({_MIC_ERROR})"}
    seconds = min(max(float(seconds or 5.0), 1.0), 30.0)
    import threading as _th

    tried = []
    for device in _candidate_inputs() or [None]:
        out: dict = {}
        worker = _th.Thread(target=_record_once,
                            args=(device, seconds, samplerate, out), daemon=True)
        worker.start()
        worker.join(timeout=seconds + 10.0)
        try:
            sd.stop()
        except Exception:
            pass
        if worker.is_alive() or "samples" not in out:
            tried.append(device)
            continue
        samples = out["samples"].astype(np.float64)
        if MIC_GAIN and MIC_GAIN != 1.0:
            samples = np.clip(samples * MIC_GAIN, -32768, 32767).astype(np.int16)
        else:
            samples = samples.astype(np.int16)
        peak = int(abs(samples).max()) if len(samples) else 0
        rms = float((np.abs(samples.astype(np.float64) ** 2).mean()) ** 0.5)
        return {"success": True, "samples": samples, "samplerate": samplerate,
                "seconds": seconds, "peak": peak, "rms": round(rms, 1),
                "device": device}
    err = "no microphone responded"
    if out.get("error"):
        err = out["error"]
    logger.warning(f"mic capture failed (tried {tried}): {err}")
    return {"success": False, "error": f"{err} (tried devices {tried})"}


def heard(samples, silence_rms: float = 120.0) -> bool:
    """Energy gate: was anything actually said?
    Calibrated 2026-09: room floor ~35 ungained (~70 at 2x gain)."""
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
               samplerate: int = 16000, vad: bool = True) -> Dict[str, Any]:
    """Speech → text, local whisper. Empty speech → text '' (not an error)."""
    if not _STT_AVAILABLE:
        return {"success": False, "error": f"faster-whisper missing ({_STT_ERROR})"}
    try:
        if wav_path is None:
            if samples is None:
                return {"success": False, "error": "Nothing to transcribe."}
            wav_path = save_wav(samples, samplerate)
        model = _get_model()
        # VAD prefilter: music/silence segments never reach the decoder,
        # which is where tiny-model hallucinations come from.
        segments, info = model.transcribe(wav_path, beam_size=5, vad_filter=vad)
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
    # Loud but VAD-empty = over-aggressive filter, not silence: decode direct.
    if res.get("success") and not res.get("text") and cap.get("rms", 0) > 300:
        res = transcribe(samples=cap["samples"], samplerate=cap["samplerate"],
                         vad=False)
        res["vad_fallback"] = True
    res["rms"] = cap["rms"]
    res["samples"] = cap["samples"]  # owner-gate needs the raw audio
    res["samplerate"] = cap["samplerate"]
    return res
