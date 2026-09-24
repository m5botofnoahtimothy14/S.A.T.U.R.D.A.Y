"""SATURDAY Identity — who is looking at me, who is talking to me. All local.

FaceGallery (LBPH, ships with OpenCV-contrib):
  enroll(name, crops)     : train from grayscale face crops (200x200).
  recognize(face_crop)    : (name|None, confidence). Lower distance = surer.
  Crops persist ENCRYPTED as vault entries (tag:identity/<name>); the
  recognizer re-trains from them at boot. Nothing plaintext on disk.

VoicePrint (classical MFCC stats, numpy+scipy only — no torch needed):
  mfcc_print(samples_16k) : 26-dim unit vector (13 means + 13 stds).
  enroll(samples_list)    : averaged voiceprint, encrypted to vault.
  verify(samples)         : cosine distance vs enrolled (< 0.28 = match).
  Honest scope: owner-vs-guest check on short phrases, same mic. Scores
  always reported; never a silent yes.

Thresholds are conservative: strangers read as unknown, not as you.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("SATURDAY.Identity")

try:
    import cv2
    import numpy as np

    _CV_AVAILABLE = True
    _HAS_LBPH = hasattr(cv2, "face")
except Exception:
    cv2 = None
    np = None
    _CV_AVAILABLE = False
    _HAS_LBPH = False

try:
    from scipy.fft import dct as _dct

    _SCIPY_FFT = True
except Exception:
    _dct = None
    _SCIPY_FFT = False

FACE_SIZE = 200
LBPH_THRESHOLD = 55.0  # LBPH distance: below = recognized. Strict: real
# same-person reads land ~10-45 with varied enrollment crops; strangers
# read far higher. Distances are always reported so you can judge.
VOICE_THRESHOLD = 0.28  # fallback voice cosine threshold (enroll calibrates personal)


class FaceGallery:
    def __init__(self, load_fn: Optional[Callable[[], Dict[str, list]]] = None,
                 save_fn: Optional[Callable[[str, bytes], None]] = None):
        """load_fn() → {name: [png_bytes, ...]}; save_fn(name, png_bytes)."""
        self.names: List[str] = []
        self.recognizer = None
        self.trained_at = 0.0
        if not (_CV_AVAILABLE and _HAS_LBPH):
            logger.warning("cv2.face LBPH missing — face identity offline.")
            return
        try:
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        except Exception as e:
            logger.warning(f"LBPH init failed — face identity offline ({e}).")
            return
        if load_fn:
            try:
                self.train(load_fn())
            except Exception as e:
                logger.warning(f"Gallery train failed: {e}")

    def available(self) -> bool:
        return self.recognizer is not None

    @staticmethod
    def norm(crop) -> Optional[bytes]:
        """Face crop → 200x200 grayscale PNG bytes."""
        try:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
            small = cv2.resize(gray, (FACE_SIZE, FACE_SIZE))
            ok, buf = cv2.imencode(".png", small)
            return buf.tobytes() if ok else None
        except Exception:
            return None

    def train(self, gallery: Dict[str, list]) -> int:
        import pickle

        if not self.available():
            return 0
        images, labels, self.names = [], [], sorted(gallery.keys())
        for idx, name in enumerate(self.names):
            for item in gallery[name]:
                raw = item
                if isinstance(item, (bytes, bytearray)):
                    if item[:8] == b"\x89PNG\r\n\x1a\n":
                        arr = cv2.imdecode(np.frombuffer(item, np.uint8), cv2.IMREAD_GRAYSCALE)
                    else:
                        try:
                            arr = pickle.loads(bytes(item))
                        except Exception:
                            continue
                else:
                    arr = np.asarray(item)
                if arr is None or arr.size == 0:
                    continue
                if arr.shape != (FACE_SIZE, FACE_SIZE):
                    arr = cv2.resize(arr, (FACE_SIZE, FACE_SIZE))
                images.append(arr.astype(np.uint8))
                labels.append(idx)
        if not images:
            return 0
        self.recognizer.train(images, np.array(labels))
        self.trained_at = time.time()
        return len(images)

    def recognize(self, crop) -> Tuple[Optional[str], float]:
        """(name or None, LBPH distance). Unknown when unsure — by design."""
        if not self.available() or not self.names:
            return None, float("inf")
        data = self.norm(crop)
        if not data:
            return None, float("inf")
        try:
            arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
            label, dist = self.recognizer.predict(arr)
            if 0 <= label < len(self.names) and dist < LBPH_THRESHOLD:
                return self.names[label], round(float(dist), 1)
            return None, round(float(dist), 1)
        except Exception as e:
            logger.debug(f"recognize failed: {e}")
            return None, float("inf")


# -- voice -------------------------------------------------------------------
def mfcc_print(samples, samplerate: int = 16000):
    """16kHz mono int16 → 26-dim unit voiceprint. Deterministic, no ML."""
    if np is None or not _SCIPY_FFT:
        raise RuntimeError("numpy/scipy required for voiceprint")
    x = np.asarray(samples, dtype=np.float64).flatten()
    if len(x) < samplerate // 2:
        raise ValueError("Need 0.5s+ of audio.")
    x = x / max(1.0, abs(x).max())
    x = np.append(x[0], x[1:] - 0.97 * x[:-1])  # pre-emphasis
    flen, hop = int(0.025 * samplerate), int(0.010 * samplerate)
    frames = [x[i:i + flen] * np.hamming(flen) for i in range(0, len(x) - flen + 1, hop)]
    if len(frames) < 5:
        raise ValueError("Audio too short for voiceprint.")
    spec = np.abs(np.fft.rfft(frames, n=512, axis=1)) ** 2
    # 26 mel filters, 80..8000 Hz
    def hz2mel(h):
        import math
        return 2595 * math.log10(1 + h / 700.0)

    def mel2hz(m):
        return 700 * (10 ** (m / 2595.0) - 1)
    lo, hi = hz2mel(80), hz2mel(8000)
    points = np.floor(257 * (mel2hz(np.linspace(lo, hi, 28)) / (samplerate / 2))).astype(int)
    points = np.clip(points, 0, 256)
    fb = np.zeros((26, 257))
    for m in range(26):
        f0, f1, f2 = points[m], points[m + 1], points[m + 2]
        if f1 > f0:
            fb[m, f0:f1] = (np.arange(f0, f1) - f0) / max(1, f1 - f0)
        if f2 > f1:
            fb[m, f1:f2] = (f2 - np.arange(f1, f2)) / max(1, f2 - f1)
    loge = np.log(np.maximum(spec @ fb.T, 1e-10))
    ceps = _dct(loge, type=2, axis=1, norm="ortho")[:, :13]
    ceps -= ceps.mean(axis=0, keepdims=True)  # cepstral mean norm
    vec = np.concatenate([ceps.mean(axis=0), ceps.std(axis=0)])
    vec = vec / max(1e-12, np.linalg.norm(vec))
    return vec


def cosine_dist(a, b) -> float:
    import math

    a = np.asarray(a, dtype=float).flatten()
    b = np.asarray(b, dtype=float).flatten()
    denom = max(1e-12, float(np.linalg.norm(a) * np.linalg.norm(b)))
    return round(float(1.0 - np.dot(a, b) / denom), 4)


class VoiceVault:
    """One enrolled owner voiceprint (encrypted at rest via caller).

    Threshold auto-calibrates from enrollment takes: same-mic takes are
    near-identical, so personal threshold = mean pairwise + margin. The
    value is stored and reported — no magic constant decides your identity.
    """

    def __init__(self):
        self.print = None
        self.threshold = VOICE_THRESHOLD

    def enroll(self, sample_lists: List[list]) -> Dict[str, Any]:
        if len(sample_lists) < 1:
            return {"success": False, "error": "No voice samples."}
        try:
            vecs = [mfcc_print(s) for s in sample_lists]
            avg = sum(vecs) / len(vecs)
            avg = avg / max(1e-12, np.linalg.norm(avg))
            self.print = avg
            pairs = [cosine_dist(vecs[i], vecs[j])
                     for i in range(len(vecs)) for j in range(i + 1, len(vecs))]
            if pairs:
                mean = sum(pairs) / len(pairs)
                var = sum((p - mean) ** 2 for p in pairs) / len(pairs)
                self.threshold = round(min(0.45, max(0.15, mean + 2 * var ** 0.5 + 0.05)), 3)
            return {"success": True, "samples": len(vecs), "threshold": self.threshold}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify(self, samples) -> Dict[str, Any]:
        if self.print is None:
            return {"success": False, "error": "No enrolled voice. Run enrollvoice first."}
        try:
            dist = cosine_dist(mfcc_print(samples), self.print)
            match = dist < self.threshold
            return {"success": True, "match": match, "distance": dist,
                    "threshold": self.threshold,
                    "verdict": "owner" if match else "guest/unknown"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def dump(self) -> dict:
        import json as _json

        return {"vector": self.print.tolist() if self.print is not None else None,
                "threshold": self.threshold}

    def load(self, data: dict) -> bool:
        try:
            if not data or data.get("vector") is None:
                return False
            self.print = np.array(data["vector"], dtype=float)
            self.threshold = float(data.get("threshold", VOICE_THRESHOLD))
            return True
        except Exception:
            return False
