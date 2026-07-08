import logging
import threading
import time
from collections import deque
from typing import Dict, Tuple

import numpy as np

SD_AVAILABLE = False
try:
    import sounddevice as sd
    SD_AVAILABLE = True
except (ImportError, OSError):
    sd = None

from core.event_bus import EventBus

logger = logging.getLogger("SATURDAY.SoundMonitor")


class SoundMonitor:
    def __init__(self, event_bus: EventBus, threshold_db: float = 55.0, window_ms: int = 400):
        self.event_bus = event_bus
        self.threshold_db = threshold_db
        self.window_ms = window_ms
        self.running = False
        self.stream = None
        self.alarm_streak = 0
        self.siren_history = deque(maxlen=8)
        self.snore_peaks = deque(maxlen=5)

    @staticmethod
    def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return float(max(lo, min(hi, v)))

    def _rms_db(self, samples: np.ndarray) -> float:
        rms = np.sqrt(np.mean(np.square(samples.astype(np.float32))))
        if rms <= 0:
            return -120.0
        return 20 * np.log10(rms + 1e-12)

    def _dominant_freq(self, samples: np.ndarray, sr: int) -> Tuple[float, float, np.ndarray]:
        window = np.hanning(len(samples))
        spec = np.fft.rfft(samples * window)
        freqs = np.fft.rfftfreq(len(samples), 1 / sr)
        mag = np.abs(spec)
        idx = int(np.argmax(mag))
        return float(freqs[idx]), float(mag[idx]), mag

    def _spectral_centroid(self, mag: np.ndarray, sr: int) -> float:
        freqs = np.linspace(0, sr / 2, len(mag))
        if mag.sum() == 0:
            return 0.0
        return float(np.sum(freqs * mag) / np.sum(mag))

    def _spectral_bandwidth(self, mag: np.ndarray, sr: int, centroid: float) -> float:
        freqs = np.linspace(0, sr / 2, len(mag))
        if mag.sum() == 0:
            return 0.0
        return float(np.sqrt(np.sum(((freqs - centroid) ** 2) * mag) / np.sum(mag)))

    def _spectral_rolloff(self, mag: np.ndarray, sr: int, pct: float = 0.85) -> float:
        if mag.size == 0:
            return 0.0
        cumsum = np.cumsum(mag)
        target = pct * cumsum[-1]
        idx = int(np.searchsorted(cumsum, target))
        idx = min(idx, len(mag) - 1)
        return float((sr / 2.0) * idx / max(1, len(mag) - 1))

    def _spectral_flatness(self, mag: np.ndarray) -> float:
        if mag.size == 0:
            return 0.0
        x = np.maximum(mag, 1e-12)
        geo = np.exp(np.mean(np.log(x)))
        arith = np.mean(x) + 1e-12
        return float(geo / arith)

    def _zero_crossing_rate(self, samples: np.ndarray) -> float:
        if samples.size < 2:
            return 0.0
        signs = np.sign(samples)
        return float(np.mean(np.abs(np.diff(signs)) > 0))

    def _band_ratios(self, mag: np.ndarray, sr: int) -> Tuple[float, float, float]:
        freqs = np.linspace(0, sr / 2, len(mag))
        total = float(np.sum(mag)) + 1e-12
        low = float(np.sum(mag[(freqs >= 20) & (freqs < 300)])) / total
        speech = float(np.sum(mag[(freqs >= 300) & (freqs < 3400)])) / total
        high = float(np.sum(mag[(freqs >= 3400) & (freqs <= sr / 2)])) / total
        return low, speech, high

    def _infer_scene(
        self,
        level_db: float,
        dom_freq: float,
        mag: np.ndarray,
        samples: np.ndarray,
        sr: int,
        centroid: float,
        bandwidth: float,
        crest: float,
    ) -> Tuple[str, float, Dict[str, float]]:
        rolloff = self._spectral_rolloff(mag, sr, pct=0.85)
        flatness = self._spectral_flatness(mag)
        zcr = self._zero_crossing_rate(samples)
        low_ratio, speech_ratio, high_ratio = self._band_ratios(mag, sr)

        speech_like = (
            300 <= centroid <= 3200
            and 450 <= bandwidth <= 3200
            and speech_ratio >= 0.33
            and level_db >= 42
        )

        scores = {
            "noise": 0.25
            + 0.45 * self._clamp(flatness)
            + 0.2 * self._clamp(1.0 - speech_ratio)
            + 0.1 * self._clamp((level_db - 40.0) / 40.0),
            "person_speaking": 0.2
            + (0.4 if speech_like else 0.0)
            + 0.2 * self._clamp(1.0 - abs(dom_freq - 180.0) / 220.0)
            + 0.1 * self._clamp(1.0 - flatness)
            + 0.1 * self._clamp((75.0 - level_db) / 35.0),
            "people_speaking": 0.1
            + (0.45 if speech_like else 0.0)
            + 0.2 * self._clamp((bandwidth - 1200.0) / 1800.0)
            + 0.15 * self._clamp(flatness / 0.6)
            + 0.1 * self._clamp((level_db - 48.0) / 25.0),
            "tv_channel": 0.1
            + (0.35 if speech_like else 0.0)
            + 0.25 * self._clamp(high_ratio / 0.35)
            + 0.15 * self._clamp((centroid - 1600.0) / 1800.0)
            + 0.15 * self._clamp((flatness - 0.2) / 0.5),
            "tv": 0.1
            + (0.3 if speech_like else 0.0)
            + 0.2 * self._clamp((high_ratio + speech_ratio) / 0.8)
            + 0.2 * self._clamp((rolloff - 2500.0) / 3000.0)
            + 0.2 * self._clamp((level_db - 45.0) / 30.0),
            "hall": 0.15
            + 0.25 * self._clamp(low_ratio / 0.5)
            + 0.25 * self._clamp((bandwidth - 900.0) / 2000.0)
            + 0.2 * self._clamp((0.55 - flatness) / 0.55)
            + 0.15 * self._clamp((4.5 - crest) / 4.5),
            "small_kids": 0.05
            + (0.35 if speech_like else 0.0)
            + 0.3 * self._clamp((dom_freq - 260.0) / 900.0)
            + 0.15 * self._clamp((centroid - 1900.0) / 2200.0)
            + 0.15 * self._clamp((zcr - 0.08) / 0.16),
        }

        label, top = max(scores.items(), key=lambda kv: kv[1])
        total = sum(max(v, 0.0) for v in scores.values()) + 1e-12
        confidence = float(max(0.0, top) / total)
        return label, confidence, scores

    def _classify(self, level_dbfs: float, dom_freq: float, dom_mag, mag, sr: int, samples: np.ndarray):
        # Convert dBFS (-inf..0) to a user-friendly positive scale (0..100-ish).
        level_db = level_dbfs + 100.0
        crest = (np.max(np.abs(mag)) + 1e-6) / (np.mean(np.abs(mag)) + 1e-6)
        centroid = self._spectral_centroid(mag, sr)
        bandwidth = self._spectral_bandwidth(mag, sr, centroid)

        scene, confidence, scene_scores = self._infer_scene(
            level_db=level_db,
            dom_freq=dom_freq,
            mag=mag,
            samples=samples,
            sr=sr,
            centroid=centroid,
            bandwidth=bandwidth,
            crest=crest,
        )

        payload = {
            "level_db": round(level_db, 1),
            "level_dbfs": round(level_dbfs, 1),
            "label": scene,
            "confidence": round(confidence, 3),
            "centroid_hz": round(centroid, 1),
            "bandwidth_hz": round(bandwidth, 1),
            "dominant_hz": int(dom_freq),
        }
        self.event_bus.publish("sound_detected", payload)
        self.event_bus.publish("acoustic_scene", {**payload, "scores": {k: round(v, 3) for k, v in scene_scores.items()}})

        scene_events = {
            "noise": "noise_detected",
            "person_speaking": "person_speaking_detected",
            "people_speaking": "people_speaking_detected",
            "tv": "tv_detected",
            "tv_channel": "tv_channel_detected",
            "hall": "hall_detected",
            "small_kids": "small_kids_detected",
        }
        self.event_bus.publish(scene_events.get(scene, "noise_detected"), payload)

        if level_db >= 80 and crest > 6:
            self.event_bus.publish("loud_noise", {"level_db": round(level_db, 1), "crest": round(crest, 2)})

        if 45 <= level_db <= 90 and 300 <= centroid <= 3000 and bandwidth > 500:
            self.event_bus.publish("speech_detected", {"level_db": round(level_db, 1), "scene": scene})

        narrow = bandwidth < 300 and 500 <= dom_freq <= 4000 and level_db >= 60
        self.alarm_streak = self.alarm_streak + 1 if narrow else 0
        if self.alarm_streak >= 3:
            self.event_bus.publish("alarm_tone", {"freq_hz": int(dom_freq), "level_db": round(level_db, 1)})

        self.siren_history.append(dom_freq)
        if len(self.siren_history) >= 6:
            diffs = np.diff(self.siren_history)
            pos = np.sum(diffs > 200)
            neg = np.sum(diffs < -200)
            if pos > 1 and neg > 1 and level_db >= 60:
                self.event_bus.publish("siren_detected", {"level_db": round(level_db, 1)})

        if 40 <= dom_freq <= 300 and level_db >= 45:
            now = time.time()
            self.snore_peaks.append(now)
            if len(self.snore_peaks) >= 3:
                intervals = np.diff(self.snore_peaks)
                if all(0.5 <= iv <= 3.0 for iv in intervals[-2:]):
                    self.event_bus.publish("snore_detected", {"level_db": round(level_db, 1)})

    def _on_audio(self, indata, frames, time_info, status):
        if not self.running:
            return
        if status:
            logger.debug(f"SoundMonitor status: {status}")
        samples = indata[:, 0].astype(np.float32)
        level_dbfs = self._rms_db(samples)
        level_db = level_dbfs + 100.0

        threshold_db = self.threshold_db
        # Backward compatibility: if config still uses negative dBFS-style values.
        if threshold_db < 0:
            threshold_db = threshold_db + 100.0

        if level_db >= threshold_db:
            sr = int(self.stream.samplerate)
            dom_freq, dom_mag, mag = self._dominant_freq(samples, sr)
            self._classify(level_dbfs, dom_freq, dom_mag, mag, sr, samples)

    def start(self):
        if self.running:
            return
        if not SD_AVAILABLE:
            logger.warning("Sound monitor unavailable: sounddevice is not installed")
            return
        self.running = True

        def _worker():
            try:
                self.stream = sd.InputStream(
                    callback=self._on_audio,
                    channels=1,
                    samplerate=16000,
                    blocksize=int(0.001 * self.window_ms * 16000),
                )
                self.stream.start()
                logger.info(f"Sound monitor started @ {self.threshold_db} dB threshold")
                while self.running:
                    sd.sleep(200)
            except Exception as e:
                logger.warning(f"Sound monitor could not start: {e}")
            finally:
                try:
                    if self.stream:
                        self.stream.stop()
                        self.stream.close()
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def stop(self):
        self.running = False
