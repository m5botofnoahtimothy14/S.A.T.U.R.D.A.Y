

import numpy as np
import logging
import threading
import queue
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("SATURDAY.Speaker")

try:
    import sounddevice as sd
    SD_AVAILABLE = True
except:
    SD_AVAILABLE = False


class AudioProfile(Enum):
    DOLBY_ATMOS = "dolby_atmos"
    DOLBY_SURROUND = "dolby_surround"  
    DOLBY_STEREO = "dolby_stereo"
    CINEMA = "cinema"
    MUSIC = "music"
    VOICE = "voice"
    CUSTOM = "custom"


@dataclass
class AudioSettings:
    master_volume: float = 1.0
    bass_gain: float = 0.0
    treble_gain: float = 0.0
    mid_gain: float = 0.0
    surround_strength: float = 0.3
    compression_ratio: float = 3.0
    noise_gate: float = -60.0
    stereo_width: float = 1.2
    clarity: float = 0.5
    loudness: float = 0.5


class DolbyProcessor:
    
    
    def __init__(self, sample_rate: int = 48000, channels: int = 2):
        self.sample_rate = sample_rate
        self.channels = channels
        self.settings = AudioSettings()
        
        self._eq_bands = 10
        self._eq_gains = np.zeros(self._eq_bands)
        self._crossover_freqs = np.array([32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000])
        
        self._compressor_threshold = -20.0
        self._compressor_attack = 0.005
        self._compressor_release = 0.1
        self._compressor_ratio = 4.0
        
        self._limiter_threshold = -1.0
        
        self._bass_boost_filter = self._create_bass_filter()
        self._treble_filter = self._create_treble_filter()
        
        self._lock = threading.Lock()
        
        logger.info(f"Dolby Processor initialized: {sample_rate}Hz, {channels}ch")
    
    def _create_bass_filter(self) -> np.ndarray:
        
        b, a = self._butter(2, 200 / (self.sample_rate / 2), btype='low')
        return b, a
    
    def _create_treble_filter(self) -> np.ndarray:
        
        b, a = self._butter(2, 4000 / (self.sample_rate / 2), btype='high')
        return b, a
    
    def _butter(self, order: int, cutoff: float, btype: str = 'low'):
        
        from scipy.signal import butter
        return butter(order, cutoff, btype=btype)
    
    def _apply_eq(self, audio: np.ndarray) -> np.ndarray:
        
        from scipy.signal import lfilter
        
        if audio.ndim == 1:
            audio = np.column_stack([audio, audio])
        
        for ch in range(audio.shape[1]):
            filtered = np.zeros_like(audio[:, ch])
            for i in range(min(self._eq_bands, len(self._crossover_freqs))):
                if self._eq_gains[i] != 0:
                    low_freq = self._crossover_freqs[i] / (self.sample_rate / 2)
                    high_freq = (self._crossover_freqs[i] * 2) / (self.sample_rate / 2) if i + 1 < len(self._crossover_freqs) else 1.0
                    high_freq = min(high_freq, 1.0)
                    
                    if low_freq < 1.0 and high_freq > 0:
                        try:
                            b, a = self._butter(2, [low_freq, high_freq], btype='band')
                            band_audio = lfilter(b, a, audio[:, ch])
                            gain = 10 ** (self._eq_gains[i] / 20.0)
                            filtered += band_audio * (gain - 1)
                        except:
                            pass
            
            audio[:, ch] = np.clip(audio[:, ch] + filtered * 0.3, -1.0, 1.0)
        
        return audio
    
    def _apply_compression(self, audio: np.ndarray) -> np.ndarray:
        
        threshold_db = self._compressor_threshold
        threshold_linear = 10 ** (threshold_db / 20.0)
        
        for ch in range(audio.shape[1] if audio.ndim > 1 else 1):
            ch_data = audio[:, ch] if audio.ndim > 1 else audio
            
            above_threshold = np.abs(ch_data) > threshold_linear
            
            compressed = ch_data.copy()
            
            if np.any(above_threshold):
                ratio = self._compressor_ratio
                excess_db = 20 * np.log10(np.abs(ch_data[above_threshold]) / threshold_linear)
                compressed[above_threshold] = np.sign(ch_data[above_threshold]) * (
                    threshold_linear * 10 ** (excess_db / ratio / 20)
                )
            
            audio[:, ch] = compressed if audio.ndim > 1 else compressed
        
        return audio
    
    def _apply_limiter(self, audio: np.ndarray) -> np.ndarray:
        
        threshold_linear = 10 ** (self._limiter_threshold / 20.0)
        
        if audio.ndim == 1:
            audio = np.clip(audio, -threshold_linear, threshold_linear)
        else:
            for ch in range(audio.shape[1]):
                audio[:, ch] = np.clip(audio[:, ch], -threshold_linear, threshold_linear)
        
        return audio
    
    def _apply_stereo_widening(self, audio: np.ndarray) -> np.ndarray:
        
        if audio.ndim < 2 or audio.shape[1] < 2:
            return audio
        
        mid = (audio[:, 0] + audio[:, 1]) / 2
        side = (audio[:, 0] - audio[:, 1]) / 2
        
        width = self.settings.stereo_width
        side_enhanced = side * width
        
        audio[:, 0] = mid + side_enhanced
        audio[:, 1] = mid - side_enhanced
        
        return audio
    
    def _apply_bass_boost(self, audio: np.ndarray) -> np.ndarray:
        
        if self.settings.bass_gain <= 0:
            return audio
        
        from scipy.signal import lfilter
        
        gain = self.settings.bass_gain
        boost = 10 ** (gain / 20.0)
        
        try:
            b, a = self._bass_boost_filter
            for ch in range(audio.shape[1] if audio.ndim > 1 else 1):
                bass = lfilter(b, a, audio[:, ch] if audio.ndim > 1 else audio)
                if audio.ndim > 1:
                    audio[:, ch] = audio[:, ch] + bass * boost * 0.5
                else:
                    audio = audio + bass * boost * 0.5
        except:
            pass
        
        return audio
    
    def _apply_surround(self, audio: np.ndarray) -> np.ndarray:
        
        if audio.ndim < 2 or self.settings.surround_strength == 0:
            return audio
        
        strength = self.settings.surround_strength
        
        delay_samples = int(self.sample_rate * 0.02)
        
        for ch in range(2):
            delayed = np.zeros_like(audio[:, ch])
            delayed[delay_samples:] = audio[:-delay_samples, ch] * strength * 0.3
            audio[:, ch] += delayed * 0.3
        
        reverb = np.random.randn(len(audio)) * strength * 0.1
        audio[:, 0] += reverb * 0.2
        audio[:, 1] += reverb * 0.2
        
        return audio
    
    def _apply_volume(self, audio: np.ndarray) -> np.ndarray:
        
        return audio * self.settings.master_volume
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        
        with self._lock:
            try:
                if audio.dtype != np.float32:
                    audio = audio.astype(np.float32)
                
                audio = audio / (np.max(np.abs(audio)) + 1e-10)
                
                audio = self._apply_bass_boost(audio)
                audio = self._apply_eq(audio)
                audio = self._apply_compression(audio)
                audio = self._apply_stereo_widening(audio)
                audio = self._apply_surround(audio)
                audio = self._apply_limiter(audio)
                audio = self._apply_volume(audio)
                
                audio = np.clip(audio, -1.0, 1.0)
                
            except Exception as e:
                logger.error(f"Dolby processing error: {e}")
            
            return audio
    
    def set_profile(self, profile: AudioProfile):
        
        profiles = {
            AudioProfile.DOLBY_ATMOS: AudioSettings(
                master_volume=1.0, bass_gain=4.0, treble_gain=2.0,
                surround_strength=0.5, stereo_width=1.5, clarity=0.8
            ),
            AudioProfile.DOLBY_SURROUND: AudioSettings(
                master_volume=1.0, bass_gain=3.0, treble_gain=1.5,
                surround_strength=0.4, stereo_width=1.3
            ),
            AudioProfile.VOICE: AudioSettings(
                master_volume=1.0, bass_gain=1.0, treble_gain=3.0,
                clarity=0.9, surround_strength=0.1
            ),
            AudioProfile.CINEMA: AudioSettings(
                master_volume=1.0, bass_gain=5.0, treble_gain=2.0,
                surround_strength=0.6, compression_ratio=4.0
            ),
        }
        
        if profile in profiles:
            self.settings = profiles[profile]
            logger.info(f"Audio profile set: {profile.value}")
    
    def set_custom(self, **kwargs):
        
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)


class SpeakerOutput:
    
    
    def __init__(self, device_index: int = None, sample_rate: int = 48000):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.channels = 2
        
        self.processor = DolbyProcessor(sample_rate, self.channels)
        self._stream = None
        self._is_playing = False
        self._lock = threading.Lock()
        
        self._audio_queue = queue.Queue(maxsize=10)
        self._playback_thread = None
        
        self._current_device = None
        
        logger.info(f"Speaker output initialized: {sample_rate}Hz, device {device_index}")
    
    def _init_stream(self):
        
        if not SD_AVAILABLE:
            logger.warning("sounddevice not available")
            return
        
        try:
            devices = sd.query_devices()
            if isinstance(devices, list):
                if self.device_index is None:
                    for d in devices:
                        if d['max_output_channels'] >= 2:
                            self.device_index = devices.index(d)
                            break
                    if self.device_index is None:
                        self.device_index = 0
            
            self._stream = sd.OutputStream(
                device=self.device_index,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                callback=self._stream_callback
            )
            
            self._current_device = sd.query_devices(self.device_index)
            logger.info(f"Speaker stream opened: {self._current_device['name']}")
            
        except Exception as e:
            logger.error(f"Stream init failed: {e}")
    
    def _stream_callback(self, outdata, frames, time_info, status):
        
        if status:
            logger.debug(f"Stream status: {status}")
        
        try:
            if not self._audio_queue.empty():
                audio = self._audio_queue.get_nowait()
                
                if audio.shape[0] < frames:
                    audio = np.pad(audio, ((0, frames - audio.shape[0]), (0, 0)), mode='constant')
                elif audio.shape[0] > frames:
                    audio = audio[:frames]
                
                processed = self.processor.process(audio)
                outdata[:] = processed
            else:
                outdata.fill(0)
                
        except queue.Empty:
            outdata.fill(0)
        except Exception as e:
            logger.error(f"Stream callback error: {e}")
            outdata.fill(0)
    
    def play(self, audio: np.ndarray, wait: bool = False):
        
        with self._lock:
            if self._stream is None:
                self._init_stream()
            
            if self._stream:
                try:
                    if audio.dtype != np.float32:
                        audio = audio.astype(np.float32)
                    
                    if audio.ndim == 1:
                        audio = np.column_stack([audio, audio])
                    
                    processed = self.processor.process(audio)
                    
                    self._audio_queue.put_nowait(processed)
                    
                    if not self._stream.active:
                        self._stream.start()
                    
                    if wait:
                        time.sleep(len(audio) / self.sample_rate)
                        
                except queue.Full:
                    logger.warning("Playback queue full")
                except Exception as e:
                    logger.error(f"Play error: {e}")
    
    def play_async(self, audio: np.ndarray):
        
        thread = threading.Thread(target=self.play, args=(audio, False), daemon=True)
        thread.start()
    
    def play_wav(self, filepath: str):
        
        import wave
        
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return
        
        try:
            with wave.open(filepath, 'rb') as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                sample_width = wf.getsampwidth()
                
                frames = wf.readframes(-1)
                
                if sample_width == 2:
                    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                else:
                    audio = np.frombuffer(frames, dtype=np.float32)
                
                if channels == 2:
                    audio = audio.reshape((-1, 2))
                else:
                    audio = np.column_stack([audio, audio])
                
                self.play(audio, wait=True)
                
        except Exception as e:
            logger.error(f"WAV play error: {e}")
    
    def stop(self):
        
        with self._lock:
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except:
                    break
            
            if self._stream:
                try:
                    self._stream.stop()
                except:
                    pass
    
    def close(self):
        
        self.stop()
        
        if self._stream:
            try:
                self._stream.close()
            except:
                pass
            self._stream = None
    
    def get_devices(self):
        
        if not SD_AVAILABLE:
            return []
        
        try:
            devices = sd.query_devices()
            return [d for d in (devices if isinstance(devices, list) else [devices]) 
                   if d['max_output_channels'] >= 2]
        except:
            return []


class SpeakerManager:
    
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._speakers: Dict[int, SpeakerOutput] = {}
        self._default_speaker: Optional[SpeakerOutput] = None
        self._lock = threading.Lock()
        
        self._init_default()
    
    def _init_default(self):
        
        try:
            self._default_speaker = SpeakerOutput()
        except Exception as e:
            logger.error(f"Default speaker init failed: {e}")
    
    def get_default(self) -> Optional[SpeakerOutput]:
        
        return self._default_speaker
    
    def get_speaker(self, device_index: int) -> Optional[SpeakerOutput]:
        
        with self._lock:
            if device_index not in self._speakers:
                try:
                    self._speakers[device_index] = SpeakerOutput(device_index)
                except Exception as e:
                    logger.error(f"Speaker creation failed: {e}")
                    return None
            
            return self._speakers[device_index]
    
    def play(self, audio: np.ndarray, device_index: int = None, wait: bool = False):
        
        speaker = self.get_speaker(device_index) if device_index else self._default_speaker
        
        if speaker:
            speaker.play(audio, wait)
    
    def set_profile(self, profile: AudioProfile):
        
        for speaker in self._speakers.values():
            speaker.processor.set_profile(profile)
        
        if self._default_speaker:
            self._default_speaker.processor.set_profile(profile)


def get_speaker_manager() -> SpeakerManager:
    
    return SpeakerManager()


def get_default_speaker() -> Optional[SpeakerOutput]:
    
    return SpeakerManager().get_default()
