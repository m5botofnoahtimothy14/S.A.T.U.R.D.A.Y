"""SATURDAY Senses — real local body sensing. Camera + signal processing, offline.

- people()    : HOG person detector (ships with OpenCV, zero downloads).
- faces()     : Haar cascade face boxes (ships with OpenCV).
- mood()      : facial-expression classifier (ONNX FER+ model file) → label +
                per-emotion scores. Honest 'model unavailable' without it.
- heart_rate(): rPPG — green-channel pulsatility from the forehead ROI over
                N seconds → BPM + confidence. Pure signal processing, no ML.
- wellness()  : composite anxiety/sadness/danger estimate from measured
                signals. WELLNESS ESTIMATE ONLY — not a medical device, never
                a diagnosis. Flags tell the user to seek a professional.
- Hydration helpers (drink log math) are pure functions; persistence lives
  in the PMV vault via core handlers.

All capture functions release the camera in `finally`. Anything that fails
returns {"success": False, "error": ...} — never raises, never fakes data.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("SATURDAY.Senses")

try:
    import cv2
    import numpy as np

    _CV_AVAILABLE = True
except Exception as e:  # pragma: no cover
    cv2 = None
    np = None
    _CV_AVAILABLE = False
    _CV_ERROR = str(e)

try:
    from scipy.signal import butter, filtfilt

    _SCIPY_AVAILABLE = True
except Exception:  # pragma: no cover
    butter = filtfilt = None
    _SCIPY_AVAILABLE = False

try:
    import onnxruntime as ort

    _ORT_AVAILABLE = True
except Exception:  # pragma: no cover
    ort = None
    _ORT_AVAILABLE = False

FERPLUS_LABELS = ["neutral", "happiness", "surprise", "sadness",
                  "anger", "disgust", "fear", "contempt"]

MOOD_MAP = {"happiness": "happy", "sadness": "sad", "surprise": "surprised",
            "anger": "angry", "fear": "anxious", "disgust": "disgusted",
            "contempt": "tense", "neutral": "neutral"}

NOT_MEDICAL = ("Wellness estimate only — not a medical device, not a diagnosis. "
               "If you feel unwell, talk to a health professional.")

_emotion_session = None


# -- camera ------------------------------------------------------------
def _need_cv() -> Optional[Dict[str, Any]]:
    if not _CV_AVAILABLE:
        return {"success": False, "error": f"OpenCV missing ({_CV_ERROR})"}
    return None


def grab_frame(timeout_s: float = 8.0):
    """Open camera, return one BGR frame. Raises RuntimeError on failure."""
    missing = _need_cv()
    if missing:
        raise RuntimeError(missing["error"])
    cap = cv2.VideoCapture(0)
    try:
        if not cap.isOpened():
            raise RuntimeError("No camera available (device 0 would not open).")
        deadline = time.time() + timeout_s
        frame = None
        while time.time() < deadline:
            ok, frame = cap.read()
            if ok and frame is not None:
                return frame
            time.sleep(0.1)
        raise RuntimeError("Camera produced no frames.")
    finally:
        cap.release()


def capture_series(seconds: float, fps_target: float = 30.0,
                   on_frame: Optional[Callable] = None) -> Tuple[list, float]:
    """Capture frames for `seconds`; returns (frames, actual_fps)."""
    missing = _need_cv()
    if missing:
        raise RuntimeError(missing["error"])
    cap = cv2.VideoCapture(0)
    frames: list = []
    try:
        if not cap.isOpened():
            raise RuntimeError("No camera available (device 0 would not open).")
        interval = 1.0 / fps_target
        end = time.time() + seconds
        while time.time() < end:
            ok, frame = cap.read()
            if ok and frame is not None:
                frames.append(frame)
                if on_frame:
                    on_frame(frame)
            time.sleep(max(0.0, interval - 0.002))
        fps = len(frames) / max(seconds, 0.1)
        return frames, fps
    finally:
        cap.release()


# -- people & faces ------------------------------------------------------
_hog = None
_face_cascade = None
_face_ok = None  # None=untested, True/False cached (a broken cascade must fail ONCE, not per frame)


def _hog_detector():
    global _hog
    if _hog is None:
        _hog = cv2.HOGDescriptor()
        _hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    return _hog


def _face_detector():
    """Haar cascade or None (missing XML in frozen builds fails once, loudly)."""
    global _face_cascade, _face_ok
    if _face_ok is False:
        return None
    if _face_cascade is None:
        path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        if not path.exists():
            _face_ok = False
            logger.warning(f"Face model XML missing: {path} (frozen build needs cv2/data).")
            return None
        _face_cascade = cv2.CascadeClassifier(str(path))
        if _face_cascade.empty():
            _face_ok = False
            _face_cascade = None
            logger.warning("Face cascade loaded empty — face detection unavailable.")
            return None
        _face_ok = True
    return _face_cascade


def find_people(frame) -> Dict[str, Any]:
    missing = _need_cv()
    if missing:
        return missing
    try:
        boxes, _ = _hog_detector().detectMultiScale(frame, winStride=(8, 8))
        people = [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)} for x, y, w, h in boxes]
        return {"success": True, "count": len(people), "boxes": people}
    except Exception as e:
        logger.warning(f"people detect failed: {e}")
        return {"success": False, "error": str(e)}


def find_faces(frame) -> Dict[str, Any]:
    missing = _need_cv()
    if missing:
        return missing
    if _face_detector() is None:
        return {"success": False, "error": "Face model unavailable (missing cascade XML)."}
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        raw = _face_detector().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                                minSize=(60, 60))
        faces = [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)} for x, y, w, h in raw]
        return {"success": True, "count": len(faces), "boxes": faces}
    except Exception as e:
        logger.warning(f"face detect failed: {e}")
        return {"success": False, "error": str(e)}


# -- mood (expression classifier) ------------------------------------------
def emotion_model_path(project_root: Optional[str] = None) -> Path:
    if project_root:
        base = Path(project_root)
    elif getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        base = Path(meipass) if meipass else Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).parent.parent
    return base / "models" / "emotion-ferplus-8.onnx"


def mood(frame, model_path: Optional[str] = None) -> Dict[str, Any]:
    """Expression → mood label + emotion scores. Needs the ONNX model file."""
    missing = _need_cv()
    if missing:
        return missing
    if not _ORT_AVAILABLE:
        return {"success": False, "error": "onnxruntime missing; pip install onnxruntime"}
    path = Path(model_path) if model_path else emotion_model_path()
    if not path.exists():
        return {"success": False, "error": (
            f"Expression model not found at {path}. Download FER+ ONNX "
            "(emotion-ferplus-8.onnx) into SATURDAY_SYSTEM/models/ to enable mood.")}
    faces = find_faces(frame)
    if not faces.get("success") or not faces["boxes"]:
        return {"success": False, "error": "No face in view for mood reading."}
    try:
        global _emotion_session
        if _emotion_session is None:
            _emotion_session = ort.InferenceSession(str(path),
                                                    providers=["CPUExecutionProvider"])
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        b = faces["boxes"][0]
        crop = gray[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]]
        small = cv2.resize(crop, (64, 64)).astype(np.float32)
        blob = small.reshape(1, 1, 64, 64)
        logits = _emotion_session.run(None, {_emotion_session.get_inputs()[0].name: blob})[0][0]
        exps = np.exp(logits - logits.max())
        probs = (exps / exps.sum()).tolist()
        scores = {FERPLUS_LABELS[i]: round(float(probs[i]), 3) for i in range(8)}
        top = max(scores, key=scores.get)
        return {"success": True, "mood": MOOD_MAP[top], "top_emotion": top,
                "confidence": scores[top], "scores": scores, "face": b}
    except Exception as e:
        logger.warning(f"mood failed: {e}")
        return {"success": False, "error": str(e)}


# -- heart rate (rPPG) -------------------------------------------------------
def forehead_series(frames: list) -> Tuple[list, int]:
    """Green-channel mean of the forehead ROI per frame. Returns (values, faces_seen)."""
    values: list = []
    if _face_detector() is None:
        return values, 0
    seen = 0
    for frame in frames:
        small = cv2.resize(frame, (320, 240))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        raw = _face_detector().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                                minSize=(50, 50))
        if len(raw) == 0:
            continue
        seen += 1
        x, y, w, h = sorted(raw, key=lambda r: r[2] * r[3], reverse=True)[0]
        y0, y1 = y + int(0.08 * h), y + int(0.25 * h)
        x0, x1 = x + int(0.25 * w), x + int(0.75 * w)
        roi = small[max(y0, 0):y1, max(x0, 0):x1]
        if roi.size == 0:
            continue
        values.append(float(roi[:, :, 1].mean()))
    return values, seen


def bpm_from_green_series(values: list, fps: float) -> Dict[str, Any]:
    """Pure estimator: green pulsatility → BPM. Unit-testable, no camera."""
    if np is None:
        return {"success": False, "error": "numpy missing"}
    if not _SCIPY_AVAILABLE:
        return {"success": False, "error": "scipy missing; pip install scipy"}
    v = np.asarray(values, dtype=float)
    n = len(v)
    if n < int(fps * 10):
        return {"success": False, "error": f"Need 10s+ of steady signal, got {n / max(fps, 1):.1f}s."}
    v = v - np.convolve(v, np.ones(max(3, int(fps))) / max(3, int(fps)), mode="same")
    # Trim edges: filter/convolution transients + camera auto-exposure
    # settling live there. A truly flat signal must read as NO pulse.
    cut_start, cut_end = int(1.5 * fps), int(0.5 * fps)
    v = v[cut_start:n - cut_end]
    n = len(v)
    if n < int(fps * 8):
        return {"success": False, "error": "Signal too short after edge trim."}
    window = np.hamming(n)
    b, a = butter(3, [0.7 / (fps / 2), 3.5 / (fps / 2)], btype="band")
    try:
        filt = filtfilt(b, a, v * window)
    except Exception as e:
        return {"success": False, "error": f"filter failed: {e}"}
    spectrum = np.abs(np.fft.rfft(filt))
    freqs = np.fft.rfftfreq(n, 1.0 / fps)
    band = (freqs >= 0.7) & (freqs <= 3.5)
    peak_power = float(spectrum[band].max()) if band.any() else 0.0
    if not band.any() or peak_power <= 1e-6:
        return {"success": False, "error": "No pulse found in signal."}
    peak = freqs[band][np.argmax(spectrum[band])]
    bpm = float(peak * 60.0)
    confidence = round(float(spectrum[band].max() / max(spectrum[band].sum(), 1e-12)), 3)
    if confidence < 0.08:
        return {"success": False, "error": (
            f"Pulse too weak (confidence {confidence:.0%}). Hold still in good light and retry.")}
    return {"success": True, "bpm": round(bpm, 1), "confidence": confidence,
            "seconds": round(n / fps, 1)}


def heart_rate(seconds: float = 20.0, frames: Optional[list] = None,
               fps: float = 0.0) -> Dict[str, Any]:
    """Camera rPPG heart-rate scan. Sit still, face the camera, good light.
    Pass pre-captured `frames` (e.g. from the session ring buffer) for an
    instant scan with zero camera re-open."""
    missing = _need_cv()
    if missing:
        return missing
    seconds = min(max(float(seconds or 20.0), 10.0), 60.0)
    if frames is None:
        try:
            frames, fps = capture_series(seconds)
        except RuntimeError as e:
            return {"success": False, "error": str(e)}
        if not frames:
            return {"success": False, "error": "No frames captured."}
    elif not fps:
        return {"success": False, "error": "fps required with pre-captured frames."}
    try:
        values, seen = forehead_series(frames)
    except Exception as e:
        return {"success": False, "error": f"face tracking failed: {e}"}
    if seen < 0.6 * len(frames):
        return {"success": False, "error": (
            f"Face visible in only {seen}/{len(frames)} frames. "
            "Hold still facing the camera in good light and retry.")}
    res = bpm_from_green_series(values, fps)
    if not res.get("success"):
        return res
    bpm = res["bpm"]
    flag = None
    if bpm < 40 or bpm > 200:
        flag = (f"Reading {bpm} BPM is outside plausible resting range — "
                "likely motion/lighting artifact. Retry holding still.")
    res["flag"] = flag
    res["note"] = NOT_MEDICAL
    return res


# -- wellness composite -------------------------------------------------------
def wellness(hr_bpm: Optional[float] = None, mood_label: Optional[str] = None,
             sad_score: float = 0.0, resting_baseline: float = 72.0) -> Dict[str, Any]:
    """Anxiety/sadness/danger estimate from MEASURED inputs. Estimates only."""
    anxiety = 12.0
    notes = []
    if hr_bpm:
        lift = max(0.0, hr_bpm - resting_baseline)
        anxiety += min(38.0, lift * 1.4)
        if lift > 25:
            notes.append(f"heart rate {hr_bpm} well above baseline {resting_baseline}")
    if mood_label in ("anxious", "angry", "tense", "disgusted"):
        anxiety += 25.0
        notes.append(f"expression reads {mood_label}")
    elif mood_label == "sad":
        anxiety += 10.0
    sadness = min(100.0, sad_score * 100.0 + (20.0 if mood_label == "sad" else 0.0))
    anxiety = round(min(100.0, anxiety), 1)
    sadness = round(sadness, 1)
    level = "calm" if anxiety < 35 else "elevated" if anxiety < 65 else "high"
    danger = None
    if hr_bpm and (hr_bpm < 40 or hr_bpm > 200):
        danger = "Heart-rate reading outside plausible range — retake; if a real symptom, seek care promptly."
    elif anxiety >= 65 and sadness >= 50:
        danger = ("Signals point to real distress. Consider reaching out to someone you trust "
                  "or a mental-health professional. You matter.")
    return {"success": True, "anxiety": anxiety, "anxiety_level": level,
            "sadness": sadness, "mood": mood_label, "hr_bpm": hr_bpm,
            "danger": danger, "notes": notes, "disclaimer": NOT_MEDICAL}


# -- hydration ("water level") --------------------------------------------------
def log_drink(entries: List[Dict[str, Any]], ml: float, now: Optional[float] = None) -> Dict[str, Any]:
    now = now if now is not None else time.time()
    ml = float(ml)
    if not 0 < ml <= 2000:
        return {"success": False, "error": "Log 1–2000 ml at a time. Usage: drink 500"}
    entry = {"ml": ml, "at": now}
    entries.append(entry)
    return {"success": True, "logged_ml": ml, "today_ml": today_total(entries, now)}


def today_total(entries: List[Dict[str, Any]], now: Optional[float] = None) -> float:
    now = now if now is not None else time.time()
    day_start = now - (now % 86400)
    return round(sum(e.get("ml", 0) for e in entries if e.get("at", 0) >= day_start), 1)


def water_status(entries: List[Dict[str, Any]], goal_ml: float = 3000.0,
                 now: Optional[float] = None) -> Dict[str, Any]:
    total = today_total(entries, now)
    pct = min(100.0, round(total / goal_ml * 100.0, 1))
    if pct >= 100:
        msg = "💧 Daily water goal met. Nice."
    elif pct >= 60:
        msg = "💧 On track — keep sipping."
    elif pct >= 25:
        msg = "💧 Getting low — have a glass of water."
    else:
        msg = "💧 Low intake today — drink some water soon."
    return {"success": True, "today_ml": total, "goal_ml": goal_ml,
            "percent": pct, "message": msg}
