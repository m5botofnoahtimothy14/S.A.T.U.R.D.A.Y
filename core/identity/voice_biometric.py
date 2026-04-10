import json
import logging
import os
import threading
import time
from typing import Dict, List, Tuple

import numpy as np

logger = logging.getLogger("AEGIS.Identity.VoiceBiometric")


class VoiceBiometricEngine:
    def __init__(self, db_path: str = "data/voice_profiles.json"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._profiles: List[Dict] = []
        self._load_profiles()

    def _load_profiles(self):
        with self._lock:
            if not os.path.exists(self.db_path):
                self._profiles = []
                return
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._profiles = data if isinstance(data, list) else []
            except Exception as e:
                logger.warning(f"Failed to load voice profiles: {e}")
                self._profiles = []

    def _save_profiles(self):
        with self._lock:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self._profiles, f, indent=2)

    def list_profiles(self, safe: bool = True) -> List[Dict]:
        with self._lock:
            out = []
            for p in self._profiles:
                item = dict(p)
                if safe and "embedding" in item:
                    item.pop("embedding", None)
                out.append(item)
            return out

    def has_profiles(self, admin_only: bool = False) -> bool:
        with self._lock:
            for p in self._profiles:
                if not isinstance(p.get("embedding"), list):
                    continue
                if admin_only and not bool(p.get("is_admin", False)):
                    continue
                return True
            return False

    @staticmethod
    def _to_float_mono(audio: np.ndarray) -> np.ndarray:
        x = np.asarray(audio)
        if x.size == 0:
            return np.zeros(0, dtype=np.float32)
        if x.ndim > 1:
            x = np.mean(x, axis=1)
        if np.issubdtype(x.dtype, np.integer):
            maxv = np.iinfo(x.dtype).max
            if maxv <= 0:
                return np.zeros_like(x, dtype=np.float32)
            x = x.astype(np.float32) / float(maxv)
        else:
            x = x.astype(np.float32)
        x = np.clip(x, -1.0, 1.0)
        return x

    @staticmethod
    def _frame_signal(x: np.ndarray, frame_len: int, hop: int) -> np.ndarray:
        if x.size < frame_len:
            pad = np.zeros(frame_len - x.size, dtype=x.dtype)
            x = np.concatenate([x, pad], axis=0)
        n_frames = 1 + (x.size - frame_len) // hop
        idx = np.arange(frame_len)[None, :] + hop * np.arange(n_frames)[:, None]
        return x[idx]

    @staticmethod
    def _overlap_add(frames: np.ndarray, hop: int, window: np.ndarray) -> np.ndarray:
        if frames.size == 0:
            return np.zeros(0, dtype=np.float32)
        frame_len = frames.shape[1]
        out_len = (frames.shape[0] - 1) * hop + frame_len
        out = np.zeros(out_len, dtype=np.float32)
        norm = np.zeros(out_len, dtype=np.float32)
        win = window.astype(np.float32)
        for i, frame in enumerate(frames):
            start = i * hop
            end = start + frame_len
            out[start:end] += frame.astype(np.float32) * win
            norm[start:end] += win * win
        norm = np.maximum(norm, 1e-6)
        return out / norm

    @staticmethod
    def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return float(max(lo, min(hi, v)))

    def enhance_voice(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        x = self._to_float_mono(audio)
        if x.size == 0:
            return x
        x = x - np.mean(x)

        if x.size < int(0.1 * sample_rate):
            peak = float(np.max(np.abs(x))) if x.size else 0.0
            if peak > 1e-6:
                x = x / peak * 0.95
            return x.astype(np.float32)

        # Simple pre-emphasis to suppress low-frequency rumble.
        x = np.append(x[0], x[1:] - 0.97 * x[:-1]).astype(np.float32)

        frame_len = max(256, int(0.02 * sample_rate))
        hop = max(80, frame_len // 2)
        window = np.hanning(frame_len).astype(np.float32)
        frames = self._frame_signal(x, frame_len, hop)

        spec = np.fft.rfft(frames * window[None, :], axis=1)
        mag = np.abs(spec)
        phase = np.angle(spec)

        energy = np.mean(frames * frames, axis=1)
        noise_count = max(1, int(0.2 * len(energy)))
        noise_idx = np.argsort(energy)[:noise_count]
        noise_profile = np.mean(mag[noise_idx], axis=0)

        subtracted = np.maximum(mag - 1.05 * noise_profile[None, :], 0.08 * mag)

        # Energy-based gate to reduce non-voice segments while preserving continuity.
        rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
        floor = float(np.percentile(rms, 20))
        gate = np.clip((rms - floor) / (2.5 * floor + 1e-6), 0.2, 1.0).astype(np.float32)
        subtracted *= gate[:, None]

        clean_spec = subtracted * np.exp(1j * phase)
        clean_frames = np.fft.irfft(clean_spec, n=frame_len, axis=1).astype(np.float32)
        y = self._overlap_add(clean_frames, hop, window)

        peak = float(np.max(np.abs(y))) if y.size else 0.0
        if peak > 1e-6:
            y = y / peak * 0.95
        return y.astype(np.float32)

    def _extract_embedding(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        x = self.enhance_voice(audio, sample_rate)
        if x.size == 0:
            return np.zeros(31, dtype=np.float32)

        frame_len = max(320, int(0.025 * sample_rate))
        hop = max(160, int(0.01 * sample_rate))
        window = np.hanning(frame_len).astype(np.float32)
        frames = self._frame_signal(x, frame_len, hop)
        wframes = frames * window[None, :]

        rms = np.sqrt(np.mean(wframes * wframes, axis=1) + 1e-12)
        zcr = np.mean(np.abs(np.diff(np.sign(wframes), axis=1)), axis=1) * 0.5

        spec = np.fft.rfft(wframes, axis=1)
        mag = np.abs(spec) + 1e-8
        power = mag * mag
        freqs = np.fft.rfftfreq(frame_len, d=1.0 / sample_rate)

        centroid = np.sum(freqs[None, :] * mag, axis=1) / np.sum(mag, axis=1)
        bandwidth = np.sqrt(
            np.sum(((freqs[None, :] - centroid[:, None]) ** 2) * mag, axis=1)
            / np.sum(mag, axis=1)
        )

        cumulative = np.cumsum(power, axis=1)
        rolloff_bins = np.argmax(cumulative >= (0.85 * cumulative[:, -1][:, None]), axis=1)
        rolloff = freqs[rolloff_bins]

        def band_ratio(f_lo: float, f_hi: float) -> float:
            mask = (freqs >= f_lo) & (freqs < f_hi)
            if not np.any(mask):
                return 0.0
            e_band = float(np.mean(np.sum(power[:, mask], axis=1)))
            e_total = float(np.mean(np.sum(power, axis=1))) + 1e-8
            return e_band / e_total

        low_ratio = band_ratio(20, 300)
        speech_ratio = band_ratio(300, 3400)
        high_ratio = band_ratio(3400, 8000)
        voiced_ratio = float(np.mean(rms > np.percentile(rms, 35)))
        peak_to_rms = float(np.max(np.abs(x)) / (np.sqrt(np.mean(x * x)) + 1e-8))

        log_power = np.log1p(np.mean(power, axis=0))
        band_chunks = np.array_split(log_power, 16)
        spectral_bands = np.array([float(np.mean(c)) for c in band_chunks], dtype=np.float32)

        feats = np.array(
            [
                float(np.mean(rms)),
                float(np.std(rms)),
                float(np.mean(zcr)),
                float(np.std(zcr)),
                float(np.mean(centroid)) / (sample_rate / 2.0 + 1e-6),
                float(np.std(centroid)) / (sample_rate / 2.0 + 1e-6),
                float(np.mean(bandwidth)) / (sample_rate / 2.0 + 1e-6),
                float(np.std(bandwidth)) / (sample_rate / 2.0 + 1e-6),
                float(np.mean(rolloff)) / (sample_rate / 2.0 + 1e-6),
                float(np.std(rolloff)) / (sample_rate / 2.0 + 1e-6),
                low_ratio,
                speech_ratio,
                high_ratio,
                voiced_ratio,
                peak_to_rms / 8.0,
            ],
            dtype=np.float32,
        )
        emb = np.concatenate([feats, spectral_bands], axis=0)

        emb = np.nan_to_num(emb, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
        norm = float(np.linalg.norm(emb))
        if norm > 1e-8:
            emb = emb / norm
        return emb

    def enroll_profile(
        self,
        name: str,
        audio: np.ndarray,
        sample_rate: int,
        is_admin: bool = False,
    ) -> Dict:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Profile name is required")

        emb = self._extract_embedding(audio, sample_rate).tolist()

        with self._lock:
            existing = None
            for p in self._profiles:
                if str(p.get("name", "")).strip().lower() == clean_name.lower():
                    existing = p
                    break

            if existing is None:
                max_id = 0
                for p in self._profiles:
                    try:
                        max_id = max(max_id, int(p.get("id", 0)))
                    except Exception:
                        continue
                existing = {
                    "id": max_id + 1,
                    "name": clean_name,
                    "samples": 0,
                }
                self._profiles.append(existing)

            prev_emb = existing.get("embedding")
            prev_samples = int(existing.get("samples", 0) or 0)
            if isinstance(prev_emb, list) and len(prev_emb) == len(emb) and prev_samples > 0:
                blended = (
                    (np.asarray(prev_emb, dtype=np.float32) * float(prev_samples) + np.asarray(emb, dtype=np.float32))
                    / float(prev_samples + 1)
                )
                norm = float(np.linalg.norm(blended))
                if norm > 1e-8:
                    blended = blended / norm
                emb = blended.tolist()

            existing["embedding"] = emb
            existing["samples"] = prev_samples + 1
            existing["sample_rate"] = int(sample_rate)
            existing["trained"] = True
            existing["is_admin"] = bool(is_admin or existing.get("is_admin", False))
            existing["updated_at"] = time.time()

            self._save_profiles()
            return dict(existing)

    def verify_speaker(
        self,
        audio: np.ndarray,
        sample_rate: int,
        threshold: float = 0.72,
        admin_only: bool = False,
    ) -> Dict:
        emb = self._extract_embedding(audio, sample_rate)
        best_name = None
        best_score = -1.0
        best_admin = False

        with self._lock:
            for p in self._profiles:
                db_emb = p.get("embedding")
                if not isinstance(db_emb, list):
                    continue
                if admin_only and not bool(p.get("is_admin", False)):
                    continue
                db_vec = np.asarray(db_emb, dtype=np.float32)
                if db_vec.shape != emb.shape:
                    continue
                score = float(np.dot(emb, db_vec))
                if score > best_score:
                    best_score = score
                    best_name = p.get("name")
                    best_admin = bool(p.get("is_admin", False))

        matched = best_score >= float(threshold) and best_name is not None
        return {
            "matched": bool(matched),
            "name": best_name,
            "score": round(best_score, 4) if best_score >= 0 else -1.0,
            "threshold": float(threshold),
            "is_admin": best_admin,
        }
