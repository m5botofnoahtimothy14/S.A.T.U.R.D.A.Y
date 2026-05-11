
import logging
import threading
import numpy as np
import sounddevice as sd
from core.event_bus import EventBus

logger = logging.getLogger("SATURDAY.SpatialAudio")

class SpatialAudioEngine:
    
    def __init__(self, event_bus: EventBus, sample_rate: int = 44100):
        self.event_bus = event_bus
        self.sample_rate = sample_rate
        self.channels = 2          # Stereo baseline (expand to 5.1/7.1 if hardware supports)
        self.master_volume = 0.8
        self.active_sources: dict = {}

        self.listener = np.array([0.0, 0.0, 0.0])

        self.event_bus.subscribe("voice_response",   self._on_voice)
        self.event_bus.subscribe("security_alert",   self._on_alert)
        self.event_bus.subscribe("health_update",    self._on_health_chime)
        logger.info("Spatial Audio Engine initialized (stereo, Atmos-style routing).")

    def _pan_stereo(self, signal: np.ndarray, azimuth_deg: float) -> np.ndarray:
        
        angle = np.radians(np.clip(azimuth_deg, -90, 90))
        left_gain  = np.cos((angle + np.pi / 2) / 2)
        right_gain = np.sin((angle + np.pi / 2) / 2)
        stereo = np.column_stack([signal * left_gain, signal * right_gain])
        return stereo

    def _distance_attenuation(self, signal: np.ndarray, distance: float) -> np.ndarray:
        
        gain = 1.0 / max(1.0, distance ** 2)
        return signal * min(gain, 1.0)

    def _sine_tone(self, freq: float, duration: float, amplitude: float = 0.4) -> np.ndarray:
        
        t = np.linspace(0, duration, int(self.sample_rate * duration), endpoint=False)
        return amplitude * np.sin(2 * np.pi * freq * t).astype(np.float32)

    def _play_stereo(self, stereo: np.ndarray):
        
        threading.Thread(
            target=lambda: sd.play(stereo * self.master_volume, self.sample_rate, blocking=True),
            daemon=True
        ).start()

    def play_tonal_alert(self, azimuth_deg: float = 0.0, distance: float = 1.0,
                         freq: float = 880.0, duration: float = 0.3):
        
        logger.debug("Alert tone suppressed (muted).")
        return

    def play_startup_chime(self):
        
        logger.info("Startup chime suppressed (muted).")
        return

    def set_master_volume(self, volume: float):
        self.master_volume = np.clip(volume, 0.0, 1.0)
        logger.info(f"Master volume set to {self.master_volume:.0%}")

    def _on_voice(self, text: str):
        
        self.play_tonal_alert(azimuth_deg=0.0, distance=1.5, freq=440.0, duration=0.1)

    def _on_alert(self, data: dict):
        
        self.play_tonal_alert(azimuth_deg=60.0, distance=1.2, freq=1200.0, duration=0.4)

    def _on_health_chime(self, data: dict):
        
        self.play_tonal_alert(azimuth_deg=-30.0, distance=2.0, freq=660.0, duration=0.2)
