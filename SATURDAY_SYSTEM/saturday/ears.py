"""SATURDAY Ears — real local hearing. Mic + offline speech-to-text.

- capture()   : record N seconds from the selected mic (16kHz mono int16
                for Whisper; recorded at the device native rate then
                resampled — WASAPI devices reject 16kHz direct).
- heard()     : energy gate — silence honestly reported, never hallucinated.
- transcribe(): faster-whisper (local CPU/int8, tiny model) → text.
- hear_once() : capture → gate → transcribe, one call.
- list_mics() : available input devices (index, name, host API, channels,
                default samplerate).
- select_mic(): startup device selector (config + env override) with a live
                probe that logs "mic OK, level ..." or a no-audio warning.
- input_level_meter(): live RMS level meter for calibration.

Fully offline after the first model download (~75MB tiny). No cloud STT,
no keys, audio never leaves the PC. Failures return
{"success": False, "error": ...} — silence returns success with text "".

C: is kept clean — model cache, temp WAVs and logs default to D:.
"""

import json
import logging
import os
import tempfile
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Ears")

# -- D: defaults: C: is ~95% full, never cache there ----------------------
def _d_drive() -> Path:
    raw = os.getenv("SATURDAY_D_DRIVE", "D:/") or "D:/"
    raw = raw.replace("\\", "/")
    if len(raw) == 2 and raw[1] == ":":
        raw += "/"  # bare "D:" is drive-relative in Windows — need "D:/"
    return Path(raw)


_D_ROOT = _d_drive()
_HF_DEFAULT = str(_D_ROOT / "S.A.T.U.R.D.A.Y" / ".huggingface")
_TMP_DEFAULT = str(_D_ROOT / "SATURDAY_TEMP")
os.environ.setdefault("HF_HOME", os.getenv("HF_HOME", "") or _HF_DEFAULT)
os.environ.setdefault("XDG_CACHE_HOME",
                      os.getenv("XDG_CACHE_HOME", "") or str(_D_ROOT / ".cache"))
os.environ.setdefault("HF_HUB_CACHE",
                      os.getenv("HF_HUB_CACHE", "") or os.path.join(_HF_DEFAULT, "hub"))

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
MIC_GAIN = float(os.getenv("SATURDAY_MIC_GAIN", "") or "0") or None  # resolved lazily
MIC_DEVICE = os.getenv("SATURDAY_MIC_DEVICE", "").strip()
TARGET_SR = 16000
_stt_model = None


def _package_root() -> Path:
    return Path(__file__).parent.parent


def _audio_config() -> Dict[str, Any]:
    """settings.json [audio] section; env vars always win over it."""
    for path in (_package_root() / "config" / "settings.json",
                 Path.cwd() / "config" / "settings.json"):
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict) and isinstance(data.get("audio"), dict):
                    return data["audio"]
        except Exception:
            pass
    return {}


def _resolve_gain() -> float:
    if MIC_GAIN:
        return MIC_GAIN
    try:
        return float(_audio_config().get("mic_gain", 2.0) or 2.0)
    except Exception:
        return 2.0


def _prefer_offline_stt():
    """If a whisper model is already cached, stay offline (frozen exes and
    flaky networks must not depend on hub roundtrips to hear)."""
    try:
        hub = os.path.join(os.environ.get("HF_HOME", ""), "hub")
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


def _host_api_name(dev: dict) -> str:
    try:
        return sd.query_hostapis()[dev["hostapi"]]["name"]
    except Exception:
        return "?"


def list_mics() -> Dict[str, Any]:
    """Every input device: index, name, host API, channels, samplerate."""
    if not _MIC_AVAILABLE:
        return {"success": False, "error": f"mic backend missing ({_MIC_ERROR})"}
    try:
        devices = sd.query_devices()
        inputs = [{"index": i, "name": d["name"],
                   "host_api": _host_api_name(d),
                   "max_input_channels": d["max_input_channels"],
                   "default_samplerate": d["default_samplerate"],
                   "channels": d["max_input_channels"]}  # legacy alias
                  for i, d in enumerate(devices) if d["max_input_channels"] > 0]
        default = sd.default.device
        return {"success": True, "mics": inputs, "default": default}
    except Exception as e:
        return {"success": False, "error": str(e)}


_JUNK_NAME_BITS = ("stereo mix", "mapper", "virtual", "capturer",
                   "front panel", "mic in at")


def _is_fallback_name(name: str) -> bool:
    n = str(name or "").lower()
    return any(k in n for k in _JUNK_NAME_BITS)


def _rank_device(i: int, d: dict) -> tuple:
    """Lower tuple sorts first. WASAPI Realtek mic array wins; loopbacks,
    mappers, virtual cables and unplugged front jacks sink to the tail."""
    name = str(d.get("name", "")).lower()
    api = _host_api_name(d).lower()
    if _is_fallback_name(name):
        return (9, 0, i)
    score = 0
    if "microphone array" in name:
        score += 3
    if "microphone" in name or " mic" in name or name.startswith("mic"):
        score += 2
    if "realtek" in name:
        score += 1
    api_bonus = 0
    if "wasapi" in api:
        api_bonus = 2  # lowest latency, native rates; needs native-sr record
    elif "wdm-ks" in api:
        api_bonus = -2  # duplicates seen giving one-sided spikes; last resort
    return (0, -(score * 10 + api_bonus), i)


def _match_device(spec: str) -> Optional[int]:
    """Index ('9') or case-insensitive name substring ('wasapi array')."""
    spec = (spec or "").strip()
    if not spec:
        return None
    try:
        devices = sd.query_devices()
    except Exception:
        return None
    if spec.lstrip("-").isdigit():
        idx = int(spec)
        try:
            if devices[idx]["max_input_channels"] > 0:
                return idx
        except Exception:
            return None
        return None
    low = spec.lower()
    scored = []
    for i, d in enumerate(devices):
        try:
            if d["max_input_channels"] <= 0:
                continue
        except Exception:
            continue
        name = str(d.get("name", ""))
        full = f"{_host_api_name(d)} {name}".lower()
        if low in name.lower() or low in full:
            scored.append((_rank_device(i, d), i))
    if not scored:
        return None
    scored.sort()
    return scored[0][1]


def resolve_mic_device() -> Optional[int]:
    """Startup device selector: env SATURDAY_MIC_DEVICE wins, then
    settings.json [audio].mic_device, then auto-rank. Returns None only
    when nothing usable exists (caller falls back to the OS default)."""
    for spec in (MIC_DEVICE, str(_audio_config().get("mic_device", "") or "")):
        hit = _match_device(spec) if spec and _MIC_AVAILABLE else None
        if hit is not None:
            return hit
        if spec:
            logger.warning(f"mic selector '{spec}' matched nothing; ignoring.")
    for dev in _candidate_inputs():
        return dev
    return None


def _candidate_inputs():
    """Real mics first (WASAPI Realtek array at the head), virtual
    mappers/loopbacks/unplugged jacks last."""
    if MIC_DEVICE and MIC_DEVICE.lstrip("-").isdigit():
        return [int(MIC_DEVICE)]
    env_hit = _match_device(MIC_DEVICE) if MIC_DEVICE else None
    if env_hit is not None:
        return [env_hit]
    cfg_hit = _match_device(str(_audio_config().get("mic_device", "") or ""))
    if cfg_hit is not None:
        return [cfg_hit]
    try:
        devices = sd.query_devices()
    except Exception:
        return []
    ranked = sorted((_rank_device(i, d), i)
                    for i, d in enumerate(devices)
                    if d.get("max_input_channels", 0) > 0)
    return [i for _, i in ranked]


def _native_samplerate(device) -> float:
    try:
        return float(sd.query_devices(device)["default_samplerate"])
    except Exception:
        return 48000.0


def _watchdog_stop():
    try:
        sd.stop()
    except Exception:
        pass


def _record_native(device, seconds: float, out: dict):
    """Record at the device native rate (WASAPI Realtek rejects 16kHz
    direct with 'Invalid sample rate'). Tries native → 48k → 44.1k → 16k."""
    tried = []
    native = _native_samplerate(device)
    for sr in dict.fromkeys([native, 48000.0, 44100.0, 16000.0]):
        try:
            rec = sd.rec(int(seconds * sr), samplerate=sr,
                         channels=1, dtype="int16", device=device)
            sd.wait()
            out["samples"] = rec.flatten()
            out["recorded_sr"] = int(sr)
            return
        except Exception as e:
            tried.append(f"{int(sr)}:{str(e)[:60]}")
    out["error"] = f"no supported rate ({'; '.join(tried)})"[:200]


def _resample_to_16k(samples, src_sr: int):
    """Numpy-only down/upsample to 16kHz mono int16 (no new dependencies;
    scipy-free so the layer stays light)."""
    import numpy as _np

    x = _np.asarray(samples).astype(_np.float64).flatten()
    if int(src_sr) == TARGET_SR or len(x) < 2:
        return x.astype(_np.int16)
    n_out = max(1, int(round(len(x) * TARGET_SR / float(src_sr))))
    old_idx = _np.linspace(0.0, 1.0, len(x))
    new_idx = _np.linspace(0.0, 1.0, n_out)
    return _np.interp(new_idx, old_idx, x).astype(_np.int16)


def _apply_gain(samples):
    import numpy as _np

    gain = _resolve_gain()
    x = _np.asarray(samples).astype(_np.float64)
    if gain and gain != 1.0:
        x = _np.clip(x * gain, -32768, 32767)
    return x.astype(_np.int16), gain


def capture(seconds: float = 5.0, samplerate: int = TARGET_SR) -> Dict[str, Any]:
    """Record mono int16 audio at `samplerate` (16kHz for Whisper). Tries
    ranked mics in order. Recording runs in the CALLING thread (PortAudio
    WASAPI fails with 'Unanticipated host error' from worker threads) with
    a watchdog Timer calling sd.stop() so a dead device can never hang us."""
    if not _MIC_AVAILABLE:
        return {"success": False, "error": f"mic backend missing ({_MIC_ERROR})"}
    seconds = min(max(float(seconds or 5.0), 1.0), 30.0)
    import threading as _th

    tried = []
    out: dict = {}
    for device in _candidate_inputs() or [None]:
        out = {}
        watchdog = _th.Timer(seconds + 10.0, _watchdog_stop)
        watchdog.daemon = True
        watchdog.start()
        try:
            _record_native(device, seconds, out)
        finally:
            watchdog.cancel()
            try:
                sd.stop()
            except Exception:
                pass
        if "samples" not in out:
            tried.append(device)
            logger.warning(f"mic device {device} failed: {out.get('error')}")
            continue
        try:
            samples = _resample_to_16k(out["samples"], out.get("recorded_sr", TARGET_SR))
            samples, gain = _apply_gain(samples)
        except Exception as e:
            logger.warning(f"mic resample/gain failed (device {device}): {e}")
            tried.append(device)
            continue
        peak = int(abs(samples).max()) if len(samples) else 0
        rms = float((np.abs(samples.astype(np.float64) ** 2).mean()) ** 0.5)
        level = "OK" if rms >= 120.0 else "quiet" if rms >= 20.0 else "SILENT"
        logger.info(f"mic OK, level {level} (device {device}, "
                    f"native {out.get('recorded_sr')}Hz→16kHz, peak {peak}, rms {rms:.1f})")
        if rms < 20.0:
            logger.warning(f"no audio arrived within {seconds:.0f}s on device {device} "
                           f"(rms {rms:.1f}) — check mute / privacy / exclusive-mode hold.")
        return {"success": True, "samples": samples, "samplerate": TARGET_SR,
                "seconds": seconds, "peak": peak, "rms": round(rms, 1),
                "device": device, "recorded_sr": out.get("recorded_sr"),
                "gain": gain}
    err = "no microphone responded"
    if out.get("error"):
        err = out["error"]
    logger.warning(f"mic capture failed (tried {tried}): {err}")
    return {"success": False, "error": f"{err} (tried devices {tried})"}


def select_mic(probe_seconds: float = 1.0, verbose: bool = True) -> Dict[str, Any]:
    """Startup selector: resolve (env > config > auto), probe with a short
    recording, log 'mic OK, level X'. Call once at boot."""
    if not _MIC_AVAILABLE:
        return {"success": False, "error": f"mic backend missing ({_MIC_ERROR})"}
    device = resolve_mic_device()
    try:
        info = sd.query_devices(device) if device is not None else {"name": "OS default"}
        api = _host_api_name(sd.query_devices(device)) if device is not None else "?"
    except Exception:
        info, api = {"name": "?"}, "?"
    msg = (f"mic selected: device {device} "
           f"[{api}] {info.get('name', '?')} (native {info.get('default_samplerate', '?')}Hz)")
    logger.info(msg)
    if verbose:
        print(msg, flush=True)
    probe = capture(max(1.0, min(float(probe_seconds or 1.0), 5.0)))
    if not probe.get("success"):
        logger.warning(f"mic probe failed: {probe.get('error')}")
        if verbose:
            print(f"WARNING: mic probe failed: {probe.get('error')}", flush=True)
        return {"success": False, "device": device, "error": probe.get("error")}
    line = (f"mic OK, level rms {probe['rms']} peak {probe['peak']} "
            f"(device {probe['device']})")
    logger.info(line)
    if verbose:
        print(line, flush=True)
    if probe["rms"] < 20.0:
        warn = (f"WARNING: no audio arrived within {probe_seconds:.0f}s "
                f"(rms {probe['rms']}) — mic may be muted, blocked by privacy "
                f"settings, or held by another app.")
        logger.warning(warn)
        if verbose:
            print(warn, flush=True)
        probe["warning"] = warn
    probe["selected_device"] = device
    return probe


def input_level_meter(seconds: float = 5.0, device=None) -> Dict[str, Any]:
    """Live input level meter: prints an RMS bar ~10x/sec for calibration.
    Returns {peak, rms} over the whole window."""
    if not _MIC_AVAILABLE:
        return {"success": False, "error": f"mic backend missing ({_MIC_ERROR})"}
    import queue as _q

    seconds = min(max(float(seconds or 5.0), 1.0), 30.0)
    dev = device if device is not None else resolve_mic_device()
    sr = int(_native_samplerate(dev))
    blocks: _q.Queue = _q.Queue()
    peaks: List[float] = []
    try:
        def _cb(indata, frames, t, status):
            try:
                import numpy as _np
                b = _np.asarray(indata, dtype=_np.float64).flatten()
                rms = float((_np.abs(b ** 2).mean()) ** 0.5)
                peaks.append(float(_np.abs(b).max()))
                blocks.put(rms)
            except Exception:
                pass

        with sd.InputStream(device=dev, samplerate=sr, channels=1,
                            dtype="float32", callback=_cb):
            end = time.time() + seconds
            while time.time() < end:
                try:
                    rms = blocks.get(timeout=0.5)
                except Exception:
                    print("  [no audio callback — device silent or held]", flush=True)
                    continue
                bars = min(40, int(rms / 60))
                print(f"\r  level rms {rms:7.1f} |{'#' * bars:<40}|", end="", flush=True)
        print(flush=True)
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}
    peak = int(max(peaks)) if peaks else 0
    return {"success": True, "device": dev, "samplerate": sr,
            "peak": peak, "note": "speak during the meter; bars should move"}


def heard(samples, silence_rms: float = 120.0) -> bool:
    """Energy gate: was anything actually said?
    Calibrated 2026-09: room floor ~35 ungained (~70 at 2x gain)."""
    try:
        import numpy as _np

        rms = float((_np.abs(_np.asarray(samples).astype(_np.float64) ** 2).mean()) ** 0.5)
        return rms >= silence_rms
    except Exception:
        return False


def _temp_wav_path() -> str:
    try:
        base = Path(_TMP_DEFAULT)
        base.mkdir(parents=True, exist_ok=True)
        return str(base / f"saturday_hear_{int(time.time())}.wav")
    except Exception:
        return str(Path(tempfile.gettempdir()) / f"saturday_hear_{int(time.time())}.wav")


def save_wav(samples, samplerate: int = TARGET_SR, path: Optional[str] = None) -> str:
    if path is None:
        path = _temp_wav_path()
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
               samplerate: int = TARGET_SR, vad: bool = True) -> Dict[str, Any]:
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
                "note": (f"Silence (rms {cap['rms']}). Nothing said — no audio "
                         f"arrived within {cap.get('seconds', seconds)}s."),
                "rms": cap["rms"], "device": cap.get("device")}
    res = transcribe(samples=cap["samples"], samplerate=cap["samplerate"])
    # Loud but VAD-empty = over-aggressive filter, not silence: decode direct.
    if res.get("success") and not res.get("text") and cap.get("rms", 0) > 300:
        res = transcribe(samples=cap["samples"], samplerate=cap["samplerate"],
                         vad=False)
        res["vad_fallback"] = True
    res["rms"] = cap["rms"]
    res["samples"] = cap["samples"]  # owner-gate needs the raw audio
    res["samplerate"] = cap["samplerate"]
    res["device"] = cap.get("device")
    return res
