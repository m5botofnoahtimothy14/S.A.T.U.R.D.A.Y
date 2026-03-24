"""
Ambient sound detection for AEGIS.
Listens to the default microphone and emits structured events such as:
- sound_detected (generic)
- loud_noise / impulse
- alarm_tone (steady tone like fire/phone alarms)
- siren (rising/falling emergency pattern)
- speech_detected (human presence via voice)
- snore_detected (low-frequency repetitive pattern)
"""
import logging
import threading
import numpy as np
import sounddevice as sd
import time
from collections import deque
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.SoundMonitor")


class SoundMonitor:
    def __init__(self, event_bus: EventBus, threshold_db: float = 55.0, window_ms: int = 400):
        self.event_bus = event_bus
        self.threshold_db = threshold_db
        self.window_ms = window_ms
        self.running = False
        self.stream = None
        # Rolling state
        self.alarm_streak = 0
        self.siren_history = deque(maxlen=8)   # store recent dominant freqs
        self.snore_peaks = deque(maxlen=5)     # timestamps of low freq peaks

    def _rms_db(self, samples: np.ndarray) -> float:
        rms = np.sqrt(np.mean(np.square(samples.astype(np.float32))))
        if rms <= 0:
            return -120.0
        return 20 * np.log10(rms + 1e-12)

    def _dominant_freq(self, samples: np.ndarray, sr: int) -> float:
        # Hann window then FFT
        window = np.hanning(len(samples))
        spec = np.fft.rfft(samples * window)
        freqs = np.fft.rfftfreq(len(samples), 1 / sr)
        mag = np.abs(spec)
        idx = np.argmax(mag)
        return freqs[idx], mag[idx], mag

    def _classify(self, level_db: float, dom_freq: float, dom_mag, mag, sr: int):
        # Generic sound
        self.event_bus.publish("sound_detected", {"level_db": round(level_db, 1)})

        # Loud / impulse
        crest = (np.max(np.abs(mag)) + 1e-6) / (np.mean(np.abs(mag)) + 1e-6)
        if level_db >= 80 and crest > 6:
            self.event_bus.publish("loud_noise", {"level_db": round(level_db, 1), "crest": round(crest, 2)})

        # Speech presence (broadband, mid freq centroid)
        centroid = self._spectral_centroid(mag, sr)
        bandwidth = self._spectral_bandwidth(mag, sr, centroid)
        if 45 <= level_db <= 90 and 300 <= centroid <= 3000 and bandwidth > 500:
            self.event_bus.publish("speech_detected", {"level_db": round(level_db, 1)})

        # Alarm tone: narrow band 500-4000Hz sustained
        narrow = bandwidth < 300 and 500 <= dom_freq <= 4000 and level_db >= 60
        self.alarm_streak = self.alarm_streak + 1 if narrow else 0
        if self.alarm_streak >= 3:
            self.event_bus.publish("alarm_tone", {"freq_hz": int(dom_freq), "level_db": round(level_db, 1)})

        # Siren: alternating high/low dominant freq
        self.siren_history.append(dom_freq)
        if len(self.siren_history) >= 6:
            diffs = np.diff(self.siren_history)
            pos = np.sum(diffs > 200)
            neg = np.sum(diffs < -200)
            if pos > 1 and neg > 1 and level_db >= 60:
                self.event_bus.publish("siren_detected", {"level_db": round(level_db, 1)})

        # Snore: low freq (40-300Hz) periodic peaks
        if 40 <= dom_freq <= 300 and level_db >= 45:
            now = time.time()
            self.snore_peaks.append(now)
            if len(self.snore_peaks) >= 3:
                intervals = np.diff(self.snore_peaks)
                if all(0.5 <= iv <= 3.0 for iv in intervals[-2:]):
                    self.event_bus.publish("snore_detected", {"level_db": round(level_db, 1)})

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

    def _on_audio(self, indata, frames, time, status):  # noqa: D401
        if not self.running:
            return
        if status:
            logger.debug(f"SoundMonitor status: {status}")
        level_db = self._rms_db(indata)
        if level_db >= self.threshold_db:
            sr = int(self.stream.samplerate)
            dom_freq, dom_mag, mag = self._dominant_freq(indata[:, 0], sr)
            self._classify(level_db, dom_freq, dom_mag, mag, sr)

    def start(self):
        if self.running:
            return
        self.running = True

        def _worker():
            try:
                self.stream = sd.InputStream(callback=self._on_audio, channels=1,
                                             samplerate=16000, blocksize=int(0.001 * self.window_ms * 16000))
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
