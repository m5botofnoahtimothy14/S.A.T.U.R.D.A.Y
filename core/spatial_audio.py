# core/spatial_audio.py
"""
AEGIS Spatial Audio Engine
Provides Dolby Atmos-style 3D positional audio routing using sounddevice.
Sound sources (voice, alerts, media) are placed in virtual 3D space and
panned/filtered to create immersive directional audio.
"""
import logging
import threading
import numpy as np
import sounddevice as sd
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.SpatialAudio")

class SpatialAudioEngine:
    """
    Dolby Atmos-inspired spatial audio router.
    Places AEGIS voice, alerts and ambient sounds in a virtual 360° sound field.
    """

    def __init__(self, event_bus: EventBus, sample_rate: int = 44100):
        self.event_bus = event_bus
        self.sample_rate = sample_rate
        self.channels = 2          # Stereo baseline (expand to 5.1/7.1 if hardware supports)
        self.master_volume = 0.8
        self.active_sources: dict = {}

        # Virtual listener position (x, y, z) — centre of room
        self.listener = np.array([0.0, 0.0, 0.0])

        # Subscribe to system events that produce audio
        self.event_bus.subscribe("voice_response",   self._on_voice)
        self.event_bus.subscribe("security_alert",   self._on_alert)
        self.event_bus.subscribe("health_update",    self._on_health_chime)
        logger.info("Spatial Audio Engine initialized (stereo, Atmos-style routing).")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _pan_stereo(self, signal: np.ndarray, azimuth_deg: float) -> np.ndarray:
        """
        Equal-power stereo panning.
        azimuth_deg: -90 = hard left, 0 = centre, +90 = hard right
        """
        angle = np.radians(np.clip(azimuth_deg, -90, 90))
        left_gain  = np.cos((angle + np.pi / 2) / 2)
        right_gain = np.sin((angle + np.pi / 2) / 2)
        stereo = np.column_stack([signal * left_gain, signal * right_gain])
        return stereo

    def _distance_attenuation(self, signal: np.ndarray, distance: float) -> np.ndarray:
        """Apply inverse-square-law volume falloff based on virtual distance."""
        gain = 1.0 / max(1.0, distance ** 2)
        return signal * min(gain, 1.0)

    def _sine_tone(self, freq: float, duration: float, amplitude: float = 0.4) -> np.ndarray:
        """Generate a sine-wave tone."""
        t = np.linspace(0, duration, int(self.sample_rate * duration), endpoint=False)
        return amplitude * np.sin(2 * np.pi * freq * t).astype(np.float32)

    def _play_stereo(self, stereo: np.ndarray):
        """Play a stereo numpy array non-blocking."""
        threading.Thread(
            target=lambda: sd.play(stereo * self.master_volume, self.sample_rate, blocking=True),
            daemon=True
        ).start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def play_tonal_alert(self, azimuth_deg: float = 0.0, distance: float = 1.0,
                         freq: float = 880.0, duration: float = 0.3):
        """Beep playback disabled (muted per user request)."""
        logger.debug("Alert tone suppressed (muted).")
        return

    def play_startup_chime(self):
        """Play the AEGIS boot-up spatial audio sequence (front-centre stage)."""
        logger.info("Startup chime suppressed (muted).")
        return

    def set_master_volume(self, volume: float):
        """Set global volume 0.0–1.0."""
        self.master_volume = np.clip(volume, 0.0, 1.0)
        logger.info(f"Master volume set to {self.master_volume:.0%}")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_voice(self, text: str):
        """Voice responses come from front-centre (AEGIS speaking to you)."""
        self.play_tonal_alert(azimuth_deg=0.0, distance=1.5, freq=440.0, duration=0.1)

    def _on_alert(self, data: dict):
        """Security alerts come from the right-rear quadrant for urgency."""
        self.play_tonal_alert(azimuth_deg=60.0, distance=1.2, freq=1200.0, duration=0.4)

    def _on_health_chime(self, data: dict):
        """Health updates produce a soft left-side ambient chime."""
        self.play_tonal_alert(azimuth_deg=-30.0, distance=2.0, freq=660.0, duration=0.2)
