

import os
import sys
import logging
import threading
import queue
import json
import struct
import time
import uuid
import numpy as np
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager

logger = logging.getLogger("SATURDAY.Audio")

PLATFORM = sys.platform
IS_WINDOWS = PLATFORM.startswith("win")
IS_MAC = PLATFORM == "darwin"
IS_LINUX = PLATFORM == "linux"
IS_ANDROID = "ANDROID_ROOT" in os.environ

SD_AVAILABLE = False
try:
    import sounddevice as sd
    SD_AVAILABLE = True
except (ImportError, OSError):
    sd = None

PYAUDIO_AVAILABLE = False
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    pyaudio = None

SPEECH_RECOG_AVAILABLE = False
try:
    import speech_recognition as sr
    SPEECH_RECOG_AVAILABLE = True
except ImportError:
    sr = None

FASTER_WHISPER_AVAILABLE = False
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None

try:
    from core.identity.voice_biometric import VoiceBiometricEngine
except Exception:
    VoiceBiometricEngine = None


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class AudioBackend(Enum):
    SOUNDDEVICE = "sounddevice"
    PYAUDIO = "pyaudio"
    SPEECH_RECOG = "speech_recognition"
    DUMMY = "dummy"


@dataclass
class MicDevice:
    index: int
    name: str
    channels: int = 1
    sample_rate: int = 16000
    is_default: bool = False
    uid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    def __str__(self):
        return f"[{self.index}] {self.name} ({self.channels}ch @{self.sample_rate}Hz)"


@dataclass
class AudioChunk:
    data: np.ndarray
    sample_rate: int
    channels: int
    timestamp: float
    device_index: int
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class MicBackend:
    
    
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
        self._lock = threading.RLock()
        self._devices: Dict[int, MicDevice] = {}
        self._current_device: Optional[MicDevice] = None
        self._stream: Optional[Any] = None
        self._stream_lock = threading.Lock()
        
        self._audio_queue: queue.Queue = queue.Queue(maxsize=100)
        self._callback_queue: queue.Queue = queue.Queue(maxsize=20)
        
        self._capture_thread: Optional[threading.Thread] = None
        self._processing_thread: Optional[threading.Thread] = None
        self._is_capturing = False
        
        self._backend_type: AudioBackend = AudioBackend.DUMMY
        self._backend_lock = threading.Lock()
        
        self._error_count = 0
        self._max_errors = 5
        self._last_device_check = 0
        self._device_check_interval = 10
        
        self._callbacks: List[Callable] = []
        self._audio_buffer: List[AudioChunk] = []
        self._buffer_size = 10
        
        self._init_backends()
    
    def _init_backends(self):
        
        if SD_AVAILABLE:
            self._backend_type = AudioBackend.SOUNDDEVICE
            logger.info("Audio backend: sounddevice")
        elif PYAUDIO_AVAILABLE:
            self._backend_type = AudioBackend.PYAUDIO
            logger.info("Audio backend: pyaudio")
        elif SPEECH_RECOG_AVAILABLE:
            self._backend_type = AudioBackend.SPEECH_RECOG
            logger.info("Audio backend: speech_recognition")
        else:
            logger.warning("No audio backend available!")
        
        self._refresh_devices()
    
    def _refresh_devices(self):
        
        with self._lock:
            self._devices.clear()
            
            if SD_AVAILABLE:
                try:
                    devices = sd.query_devices()
                    default_input_idx = None
                    try:
                        default_dev = sd.default.device
                        if isinstance(default_dev, (list, tuple)) and len(default_dev) > 0:
                            default_input_idx = int(default_dev[0])
                    except Exception:
                        default_input_idx = None
                    if isinstance(devices, (list, tuple)):
                        for i, d in enumerate(devices):
                            if isinstance(d, dict) and d.get('max_input_channels', 0) > 0:
                                mic = MicDevice(
                                    index=i,
                                    name=d['name'],
                                    channels=d['max_input_channels'],
                                    sample_rate=int(d['default_samplerate']),
                                    is_default=(default_input_idx is not None and i == default_input_idx)
                                )
                                self._devices[i] = mic
                    elif isinstance(devices, dict) and devices:
                        self._devices[0] = MicDevice(
                            index=0, name=devices['name'],
                            channels=devices['max_input_channels'],
                            sample_rate=int(devices['default_samplerate']),
                            is_default=True
                        )
                    logger.info(f"Found {len(self._devices)} microphones (sounddevice)")
                except Exception as e:
                    logger.warning(f"sounddevice device detection failed: {e}")
            
            elif PYAUDIO_AVAILABLE:
                try:
                    p = pyaudio.PyAudio()
                    for i in range(p.get_device_count()):
                        info = p.get_device_info_by_index(i)
                        if info['maxInputChannels'] > 0:
                            mic = MicDevice(
                                index=i, name=info['name'],
                                channels=info['maxInputChannels'],
                                sample_rate=int(info['defaultSampleRate']),
                                is_default=(i == 0)
                            )
                            self._devices[i] = mic
                    p.terminate()
                    logger.info(f"Found {len(self._devices)} microphones (pyaudio)")
                except Exception as e:
                    logger.warning(f"pyaudio device detection failed: {e}")
            
            if not self._devices and SPEECH_RECOG_AVAILABLE:
                try:
                    names = sr.Microphone.list_microphone_names()
                    for i, name in enumerate(names):
                        self._devices[i] = MicDevice(
                            index=i, name=name,
                            channels=1, sample_rate=16000,
                            is_default=(i == 0)
                        )
                    logger.info(f"Found {len(self._devices)} microphones (speech_recognition)")
                except Exception as e:
                    logger.warning(f"speech_recog device detection failed: {e}")
            
            if not self._devices:
                self._devices[0] = MicDevice(index=0, name="Default Microphone")
                logger.warning("No microphones detected, using default")
    
    @property
    def backend(self) -> AudioBackend:
        return self._backend_type
    
    def get_devices(self) -> List[MicDevice]:
        
        with self._lock:
            return list(self._devices.values())
    
    def get_current_device(self) -> Optional[MicDevice]:
        
        return self._current_device
    
    def set_device(self, device_index: int) -> bool:
        
        with self._lock:
            if device_index not in self._devices:
                logger.error(f"Device {device_index} not found")
                return False
            
            self._current_device = self._devices[device_index]
            logger.info(f"Switched to microphone: {self._current_device}")
            return True
    
    def auto_select_device(self) -> bool:
        
        with self._lock:
            if not self._devices:
                return False
            
            preferred_names = ['array', 'realtek', 'built-in', 'usb', 'headset', 'bluetooth']
            
            for pref in preferred_names:
                for idx, mic in self._devices.items():
                    if pref.lower() in mic.name.lower():
                        self._current_device = mic
                        logger.info(f"Auto-selected: {mic}")
                        return True
            
            for idx, mic in self._devices.items():
                if mic.is_default:
                    self._current_device = mic
                    logger.info(f"Auto-selected default: {mic}")
                    return True
            
            self._current_device = list(self._devices.values())[0]
            logger.info(f"Auto-selected first device: {self._current_device}")
            return True
    
    def check_device_changes(self) -> bool:
        
        current_time = time.time()
        if current_time - self._last_device_check < self._device_check_interval:
            return False
        
        self._last_device_check = current_time
        old_devices = set(self._devices.keys())
        self._refresh_devices()
        new_devices = set(self._devices.keys())
        
        removed = old_devices - new_devices
        added = new_devices - old_devices
        
        if removed or added:
            logger.info(f"Device change detected: removed={removed}, added={added}")
            
            if self._current_device and self._current_device.index in new_devices:
                return False
            
            logger.warning("Current device removed, auto-selecting new device")
            return self.auto_select_device()
        
        return False
    
    def register_callback(self, callback: Callable):
        
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable):
        
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _process_audio_chunk(self, chunk: AudioChunk):
        
        for callback in self._callbacks:
            try:
                callback(chunk)
            except Exception as e:
                logger.error(f"Audio callback error: {e}")
    
    def start_capture(self, device_index: Optional[int] = None, 
                     sample_rate: int = 16000,
                     chunk_duration: float = 0.1) -> bool:
        
        with self._stream_lock:
            if self._is_capturing:
                logger.warning("Capture already running")
                return True
            
            if device_index is not None:
                self.set_device(device_index)
            elif not self._current_device:
                self.auto_select_device()
            
            if not self._current_device:
                logger.error("No microphone device available")
                return False
            
            self._is_capturing = True
            self._sample_rate = sample_rate
            self._chunk_samples = int(sample_rate * chunk_duration)
            
            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                name=f"AudioCapture-{self._current_device.index}",
                daemon=True
            )
            self._capture_thread.start()
            
            logger.info(f"Audio capture started on {self._current_device}")
            return True
    
    def stop_capture(self):
        
        self._is_capturing = False
        
        with self._stream_lock:
            if self._stream:
                try:
                    self._stream.close()
                except:
                    pass
                self._stream = None
        
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2)
        
        logger.info("Audio capture stopped")
    
    def _capture_loop(self):
        
        thread_name = threading.current_thread().name
        logger.debug(f"{thread_name} started")
        
        consecutive_errors = 0
        max_consecutive = 10
        
        while self._is_capturing:
            try:
                self.check_device_changes()
                
                if not SD_AVAILABLE:
                    self._capture_fallback()
                    continue
                
                with self._stream_lock:
                    if self._stream is None or not self._stream.active:
                        device_idx = self._current_device.index if self._current_device else None
                        
                        try:
                            self._stream = sd.InputStream(
                                device=device_idx,
                                channels=1,
                                samplerate=self._sample_rate,
                                blocksize=self._chunk_samples,
                                dtype='int16',
                                callback=self._audio_callback
                            )
                            self._stream.start()
                            consecutive_errors = 0
                            logger.debug(f"{thread_name} stream opened")
                        except Exception as e:
                            logger.error(f"Stream open failed: {e}")
                            time.sleep(1)
                            continue
                
                time.sleep(0.1)
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"{thread_name} error: {e}")
                
                if consecutive_errors >= max_consecutive:
                    logger.error(f"{thread_name} too many errors, stopping")
                    break
                
                time.sleep(0.5)
        
        logger.debug(f"{thread_name} stopped")
    
    def _audio_callback(self, indata, frames, time_info, status):
        
        if status:
            logger.debug(f"Audio status: {status}")
        
        try:
            audio_data = indata[:, 0].copy()
            
            chunk = AudioChunk(
                data=audio_data,
                sample_rate=self._sample_rate,
                channels=1,
                timestamp=time.time(),
                device_index=self._current_device.index if self._current_device else 0
            )
            
            try:
                self._audio_queue.put_nowait(chunk)
            except queue.Full:
                try:
                    self._audio_queue.get_nowait()
                    self._audio_queue.put_nowait(chunk)
                except:
                    pass
            
            self._process_audio_chunk(chunk)
            
        except Exception as e:
            logger.error(f"Callback error: {e}")
    
    def _capture_fallback(self):
        
        if not SPEECH_RECOG_AVAILABLE:
            return
        
        try:
            with sr.Microphone(device_index=self._current_device.index, 
                             sample_rate=self._sample_rate) as source:
                audio = self._recognizer.listen(source, timeout=1, phrase_time_limit=3)
                
                chunk = AudioChunk(
                    data=np.zeros(self._chunk_samples, dtype=np.int16),
                    sample_rate=self._sample_rate,
                    channels=1,
                    timestamp=time.time(),
                    device_index=self._current_device.index if self._current_device else 0
                )
                self._process_audio_chunk(chunk)
                
        except Exception as e:
            logger.debug(f"SR capture: {e}")
    
    def get_audio_queue(self) -> queue.Queue:
        
        return self._audio_queue
    
    def is_capturing(self) -> bool:
        
        return self._is_capturing
    
    def get_stats(self) -> Dict[str, Any]:
        
        return {
            "backend": self._backend_type.value,
            "capturing": self._is_capturing,
            "devices": len(self._devices),
            "current_device": str(self._current_device) if self._current_device else None,
            "queue_size": self._audio_queue.qsize(),
            "callbacks": len(self._callbacks)
        }


class AudioProcessor:
    
    
    def __init__(self, mic_backend: MicBackend):
        self._mic = mic_backend
        self._recognizer = None
        self._whisper_model = None
        self._voice_biometrics = None
        self._lock = threading.Lock()
        
        self._process_queue: queue.Queue = queue.Queue(maxsize=50)
        self._result_queue: queue.Queue = queue.Queue(maxsize=20)
        
        self._processing_thread: Optional[threading.Thread] = None
        self._is_processing = False
        
        self._callbacks: List[Callable[[str], None]] = []
        self._voice_threshold = float(os.getenv("VOICE_BIOMETRIC_THRESHOLD", "0.72"))
        self._voice_admin_only = _env_flag("VOICE_BIOMETRIC_ADMIN_ONLY", True)
        self._voice_required = _env_flag("VOICE_BIOMETRIC_REQUIRED", True)
        self._last_speaker: Dict[str, Any] = {}
        
        self._init_recognizer()
    
    def _init_recognizer(self):
        
        if SPEECH_RECOG_AVAILABLE:
            try:
                self._recognizer = sr.Recognizer()
                self._recognizer.energy_threshold = 200
                self._recognizer.dynamic_energy_threshold = True
                self._recognizer.pause_threshold = 0.3
                self._recognizer.dynamic_energy_adjustment_damping = 0.15
                self._recognizer.dynamic_energy_ratio = 1.5
                logger.info("Speech recognizer initialized")
            except Exception as e:
                logger.error(f"Recognizer init failed: {e}")
        
        if FASTER_WHISPER_AVAILABLE:
            try:
                model_size = os.getenv("WHISPER_MODEL_SIZE", "tiny")
                device = os.getenv("WHISPER_DEVICE", "cpu")
                compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
                
                self._whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
                logger.info(f"Whisper model loaded: {model_size} on {device}")
            except Exception as e:
                logger.error(f"Whisper init failed: {e}")

        if VoiceBiometricEngine and _env_flag("VOICE_BIOMETRIC_ENABLED", True):
            try:
                db_path = os.getenv("VOICE_PROFILES_FILE", "data/voice_profiles.json")
                self._voice_biometrics = VoiceBiometricEngine(db_path=db_path)
                logger.info(f"Voice biometric enabled (db={db_path})")
            except Exception as e:
                logger.warning(f"Voice biometric init failed: {e}")
                self._voice_biometrics = None
    
    def register_result_callback(self, callback: Callable[[str], None]):
        
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def start_processing(self):
        
        if self._is_processing:
            return
        
        self._is_processing = True
        self._processing_thread = threading.Thread(
            target=self._processing_loop,
            name="AudioProcessor",
            daemon=True
        )
        self._processing_thread.start()
        logger.info("Audio processor started")
    
    def stop_processing(self):
        
        self._is_processing = False
        
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=2)
        
        logger.info("Audio processor stopped")
    
    def _processing_loop(self):
        
        logger.debug("AudioProcessor loop started")
        
        while self._is_processing:
            try:
                chunk = self._mic.get_audio_queue().get(timeout=0.5)
                
                text = self._recognize(chunk)
                
                if text:
                    for callback in self._callbacks:
                        try:
                            callback(text)
                        except Exception as e:
                            logger.error(f"Result callback error: {e}")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Processing error: {e}")
        
        logger.debug("AudioProcessor loop stopped")
    
    def _recognize(self, chunk: AudioChunk) -> str:
        
        if not chunk.data.size:
            return ""
        
        audio_np = chunk.data.astype(np.float32)
        if np.issubdtype(chunk.data.dtype, np.integer):
            audio_np = audio_np / 32768.0
        audio_np = np.clip(audio_np, -1.0, 1.0)

        if self._voice_biometrics:
            try:
                audio_np = self._voice_biometrics.enhance_voice(audio_np, chunk.sample_rate)
                if self._voice_biometrics.has_profiles(admin_only=self._voice_admin_only):
                    self._last_speaker = self._voice_biometrics.verify_speaker(
                        audio_np,
                        chunk.sample_rate,
                        threshold=self._voice_threshold,
                        admin_only=self._voice_admin_only,
                    )
                    if self._voice_required and not self._last_speaker.get("matched", False):
                        logger.info(
                            "Voice rejected (speaker mismatch)",
                            extra={"score": self._last_speaker.get("score"), "threshold": self._voice_threshold},
                        )
                        return ""
            except Exception as e:
                logger.debug(f"Voice biometric preprocessing failed: {e}")
        
        if self._whisper_model:
            try:
                segments, _ = self._whisper_model.transcribe(
                    audio_np,
                    language="en",
                    beam_size=1,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=300)
                )
                
                text = " ".join(s.text.strip() for s in segments if s.text.strip())
                if text:
                    logger.debug(f"Whisper: {text}")
                    return text.lower()
                    
            except Exception as e:
                logger.debug(f"Whisper recognition failed: {e}")

        if self._recognizer:
            try:
                pcm16 = np.clip(audio_np, -1.0, 1.0)
                pcm16 = (pcm16 * 32767.0).astype(np.int16)
                audio = sr.AudioData(pcm16.tobytes(), chunk.sample_rate, 2)
                result = self._recognizer.recognize_google(audio)
                if result:
                    return result.lower()
            except Exception as e:
                logger.debug(f"Google recognition failed: {e}")
        
        return ""
    
    def recognize_from_wav(self, wav_data: bytes) -> str:
        
        if not self._recognizer:
            return ""
        
        try:
            import io
            audio = sr.AudioData(wav_data, 16000, 2)
            
            result = self._recognizer.recognize_google(audio)
            return result.lower()
        except Exception as e:
            logger.debug(f"SR recognition failed: {e}")
        
        return ""


class AudioPlayer:
    
    
    def __init__(self):
        self._lock = threading.Lock()
        self._playback_queue: queue.Queue = queue.Queue(maxsize=10)
        self._playback_thread: Optional[threading.Thread] = None
        self._is_playing = False
        self.sample_rate = 22050
        self._current_stream = None
        self._init_player()
    
    def _init_player(self):
        if SD_AVAILABLE:
            try:
                sd.default.samplerate = self.sample_rate
                logger.info("Audio player ready (sounddevice)")
                return
            except Exception as e:
                logger.warning(f"sounddevice init failed: {e}")
        
        logger.info("Audio player ready (fallback)")
    
    def play_audio(self, audio_data: np.ndarray, sample_rate: int = None) -> bool:
        
        if SD_AVAILABLE:
            try:
                sr = sample_rate or self.sample_rate
                sd.play(audio_data, sr)
                sd.wait()
                return True
            except Exception as e:
                logger.error(f"Audio playback failed: {e}")
        return False
    
    def play_async(self, audio_data: np.ndarray, sample_rate: int = None):
        
        try:
            self._playback_queue.put_nowait((audio_data, sample_rate or self.sample_rate))
            
            if not self._is_playing:
                self._is_playing = True
                self._playback_thread = threading.Thread(
                    target=self._playback_loop,
                    name="AudioPlayer",
                    daemon=True
                )
                self._playback_thread.start()
        except queue.Full:
            logger.warning("Playback queue full, dropping audio")
    
    def _playback_loop(self):
        
        while self._is_playing:
            try:
                audio_data, sr = self._playback_queue.get(timeout=0.5)
                self.play_audio(audio_data, sr)
            except queue.Empty:
                if self._playback_queue.empty():
                    self._is_playing = False
                    break
            except Exception as e:
                logger.error(f"Playback error: {e}")
    
    def play_wav_file(self, filepath: str) -> bool:
        
        if not os.path.exists(filepath):
            return False
        
        if SD_AVAILABLE:
            try:
                import wave
                with wave.open(filepath, 'rb') as wf:
                    sr = wf.getframerate()
                    data = wf.readframes(-1)
                    audio_np = np.frombuffer(data, dtype=np.int16)
                    return self.play_audio(audio_np, sr)
            except Exception as e:
                logger.error(f"WAV playback failed: {e}")
        
        return False
    
    def stop(self):
        
        self._is_playing = False
        while not self._playback_queue.empty():
            try:
                self._playback_queue.get_nowait()
            except:
                break
        
        if SD_AVAILABLE:
            try:
                sd.stop()
            except:
                pass


class CrossPlatformAudio:
    
    
    def __init__(self):
        self._backend = MicBackend()
        self.whisper_model = None
        self.recognizer = None
        self.mic = None
        self.mic_index = None
        self.mics = []
        self.sample_rate = 16000
        self.voice_biometrics = None
        self.voice_biometric_threshold = float(os.getenv("VOICE_BIOMETRIC_THRESHOLD", "0.72"))
        self.voice_biometric_admin_only = _env_flag("VOICE_BIOMETRIC_ADMIN_ONLY", True)
        self.voice_biometric_required = _env_flag("VOICE_BIOMETRIC_REQUIRED", True)
        self.last_speaker_result: Dict[str, Any] = {}
        self._init_audio()
    
    def _init_audio(self):
        self._detect_microphones()
        self._init_voice_biometric()
        self._init_whisper()
        self._init_speech_recognizer()

    def _init_voice_biometric(self):
        if not VoiceBiometricEngine or not _env_flag("VOICE_BIOMETRIC_ENABLED", True):
            return
        try:
            db_path = os.getenv("VOICE_PROFILES_FILE", "data/voice_profiles.json")
            self.voice_biometrics = VoiceBiometricEngine(db_path=db_path)
            logger.info(f"Voice biometric ready (db={db_path})")
        except Exception as e:
            logger.warning(f"Voice biometric init failed: {e}")
            self.voice_biometrics = None
    
    def _detect_microphones(self):
        devices = self._backend.get_devices()
        self.mics = [(d.index, d.name) for d in devices]
        
        if self._backend.auto_select_device():
            self.mic_index = self._backend.get_current_device().index
    
    def _init_whisper(self):
        if FASTER_WHISPER_AVAILABLE:
            try:
                model_size = os.getenv("WHISPER_MODEL_SIZE", "tiny")
                device = os.getenv("WHISPER_DEVICE", "cpu")
                self.whisper_model = WhisperModel(model_size, device=device, compute_type="int8")
                logger.info(f"Whisper loaded: {model_size}")
            except Exception as e:
                logger.error(f"Whisper init failed: {e}")
    
    def _init_speech_recognizer(self):
        if SPEECH_RECOG_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.recognizer.energy_threshold = 200
                self.recognizer.dynamic_energy_threshold = True
                self.mic = sr.Microphone(device_index=self.mic_index, sample_rate=self.sample_rate)
                logger.info(f"SR ready, mic: {self.mic_index}")
            except Exception as e:
                logger.warning(f"SR init failed: {e}")
    
    def list_microphones(self):
        return self.mics

    def _audio_to_float32(self, audio_data) -> np.ndarray:
        if audio_data is None:
            return np.zeros(0, dtype=np.float32)

        if isinstance(audio_data, np.ndarray):
            arr = audio_data.astype(np.float32)
            if np.issubdtype(audio_data.dtype, np.integer):
                arr /= 32768.0
            return np.clip(arr, -1.0, 1.0)

        if SPEECH_RECOG_AVAILABLE and isinstance(audio_data, sr.AudioData):
            try:
                raw = audio_data.get_raw_data(convert_rate=self.sample_rate, convert_width=2)
                arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                return np.clip(arr, -1.0, 1.0)
            except Exception:
                try:
                    raw = audio_data.get_raw_data()
                    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    return np.clip(arr, -1.0, 1.0)
                except Exception:
                    return np.zeros(0, dtype=np.float32)

        if isinstance(audio_data, (bytes, bytearray)):
            try:
                arr = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                return np.clip(arr, -1.0, 1.0)
            except Exception:
                return np.zeros(0, dtype=np.float32)

        return np.zeros(0, dtype=np.float32)
    
    def recognize_speech(self, audio_data) -> str:
        samples = self._audio_to_float32(audio_data)
        if samples.size == 0:
            return ""

        if self.voice_biometrics:
            try:
                samples = self.voice_biometrics.enhance_voice(samples, self.sample_rate)
                if self.voice_biometrics.has_profiles(admin_only=self.voice_biometric_admin_only):
                    self.last_speaker_result = self.voice_biometrics.verify_speaker(
                        samples,
                        self.sample_rate,
                        threshold=self.voice_biometric_threshold,
                        admin_only=self.voice_biometric_admin_only,
                    )
                    if self.voice_biometric_required and not self.last_speaker_result.get("matched", False):
                        logger.info(
                            "Speech ignored (speaker mismatch)",
                            extra={"score": self.last_speaker_result.get("score"), "threshold": self.voice_biometric_threshold},
                        )
                        return ""
            except Exception as e:
                logger.debug(f"Voice biometric pipeline failed: {e}")

        if self.whisper_model:
            try:
                segments, _ = self.whisper_model.transcribe(
                    samples.astype(np.float32),
                    language=os.getenv("ASR_LANGUAGE", "en"),
                    beam_size=1,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=250),
                )
                text = " ".join(s.text.strip() for s in segments if s.text.strip())
                if text:
                    return text.lower()
            except Exception as e:
                logger.debug(f"Whisper transcription failed: {e}")

        if self.recognizer and SPEECH_RECOG_AVAILABLE:
            try:
                pcm16 = np.clip(samples, -1.0, 1.0)
                pcm16 = (pcm16 * 32767.0).astype(np.int16)
                audio = sr.AudioData(pcm16.tobytes(), self.sample_rate, 2)
                text = self.recognizer.recognize_google(audio)
                return text.lower() if text else ""
            except Exception as e:
                logger.debug(f"Google SR fallback failed: {e}")

        return ""


class AudioListener:
    
    
    def __init__(self, on_voice_callback=None):
        self._backend = MicBackend()
        self._processor = AudioProcessor(self._backend)
        self.callback = on_voice_callback
        self.listening = False
        
        if self.callback:
            self._processor.register_result_callback(self.callback)
    
    def start(self):
        if self.listening:
            return
        self.listening = True
        self._backend.start_capture()
        self._processor.start_processing()
        logger.info("Audio listener started")
    
    def stop(self):
        self.listening = False
        self._backend.stop_capture()
        self._processor.stop_processing()
        logger.info("Audio listener stopped")


audio_service = None

def get_audio_service():
    global audio_service
    if audio_service is None:
        audio_service = CrossPlatformAudio()
    return audio_service

def get_mic_backend() -> MicBackend:
    
    return MicBackend()

def get_audio_processor(backend: MicBackend = None) -> AudioProcessor:
    
    if backend is None:
        backend = get_mic_backend()
    return AudioProcessor(backend)
