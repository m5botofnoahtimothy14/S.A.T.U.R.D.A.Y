"""
Cross-Platform Audio Service
Works on Windows, macOS, Linux, Android (Termux), iOS (Pythonista)
"""
import os
import sys
import logging
import threading
import queue
import json
import struct
import numpy as np

logger = logging.getLogger("AEGIS.Audio")

PLATFORM = sys.platform
IS_WINDOWS = PLATFORM.startswith("win")
IS_MAC = PLATFORM == "darwin"
IS_LINUX = PLATFORM == "linux"
IS_ANDROID = "ANDROID_ROOT" in os.environ

SD_AVAILABLE = False
try:
    import sounddevice as sd
    SD_AVAILABLE = True
except ImportError:
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


class CrossPlatformAudio:
    def __init__(self):
        self.whisper_model = None
        self.recognizer = None
        self.mic = None
        self.mic_index = None
        self.mics = []
        self.sample_rate = 16000
        self._init_audio()
    
    def _init_audio(self):
        self._detect_microphones()
        self._init_whisper()
        self._init_speech_recognizer()
    
    def _detect_microphones(self):
        if IS_WINDOWS or IS_LINUX or IS_MAC:
            if SD_AVAILABLE:
                try:
                    devices = sd.query_devices()
                    if isinstance(devices, list):
                        self.mics = [(i, d['name']) for i, d in enumerate(devices) if d['max_input_channels'] > 0]
                    else:
                        self.mics = [(0, devices['name'])] if devices['max_input_channels'] > 0 else []
                    logger.info(f"Found {len(self.mics)} microphones (sounddevice)")
                    return
                except Exception as e:
                    logger.warning(f"sounddevice mic detection failed: {e}")
            
            if PYAUDIO_AVAILABLE:
                try:
                    p = pyaudio.PyAudio()
                    self.mics = [(i, p.get_device_info_by_index(i)['name']) 
                                 for i in range(p.get_device_count()) 
                                 if p.get_device_info_by_index(i)['maxInputChannels'] > 0]
                    p.terminate()
                    logger.info(f"Found {len(self.mics)} microphones (pyaudio)")
                    return
                except Exception as e:
                    logger.warning(f"pyaudio mic detection failed: {e}")
        
        if SPEECH_RECOG_AVAILABLE:
            try:
                self.mics = list(enumerate(sr.Microphone.list_microphone_names()))
                logger.info(f"Found {len(self.mics)} microphones (speech_recognition)")
            except Exception as e:
                logger.warning(f"speech_recog mic detection failed: {e}")
        
        if not self.mics:
            self.mics = [(0, "Default Microphone")]
            logger.warning("No microphones detected, using default")
    
    def _init_whisper(self):
        if not FASTER_WHISPER_AVAILABLE:
            logger.warning("faster-whisper not available")
            return False
        
        model_path = os.getenv("WHISPER_MODEL_PATH")
        model_size = os.getenv("WHISPER_MODEL_SIZE", "tiny")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        
        try:
            if model_path and os.path.exists(model_path):
                self.whisper_model = WhisperModel(model_path, device=device, compute_type=compute_type)
            else:
                self.whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info(f"Whisper DL model loaded: {model_size} on {device}")
            return True
        except Exception as e:
            logger.error(f"Whisper init failed: {e}")
            return False
    
    def _init_speech_recognizer(self):
        if not SPEECH_RECOG_AVAILABLE:
            return
        
        try:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 200
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.3
            
            mic_index = os.getenv("MICROPHONE_INDEX", "").strip()
            if mic_index:
                try:
                    self.mic_index = int(mic_index)
                except ValueError:
                    pass
            
            if self.mic_index is None:
                for idx, name in self.mics:
                    if "microphone" in name.lower() or "mic" in name.lower():
                        self.mic_index = idx
                        break
            
            if self.mic_index is None:
                self.mic_index = 0
            
            self.mic = sr.Microphone(device_index=self.mic_index, sample_rate=self.sample_rate)
            logger.info(f"Speech recognizer ready, using mic: {self.mics[self.mic_index] if self.mic_index < len(self.mics) else 'default'}")
        except Exception as e:
            logger.warning(f"Speech recognizer init failed: {e}")
    
    def list_microphones(self):
        return self.mics
    
    def recognize_speech(self, audio_data) -> str:
        if self.whisper_model:
            result = self._whisper_recognize(audio_data)
            if result:
                return result
        
        if self.recognizer:
            result = self._sr_recognize(audio_data)
            if result:
                return result
        
        return ""
    
    def _whisper_recognize(self, audio_data):
        try:
            if hasattr(audio_data, 'get_wav_data'):
                wav_data = audio_data.get_wav_data(convert_rate=16000, convert_width=2)
                audio_np = np.frombuffer(wav_data, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio_np = audio_data
            
            segments, _ = self.whisper_model.transcribe(
                audio_np,
                language="en",
                beam_size=1,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300)
            )
            
            text = " ".join(s.text.strip() for s in segments if s.text.strip())
            return text.strip().lower() if text else None
        except Exception as e:
            logger.debug(f"Whisper recognition failed: {e}")
        return None
    
    def _sr_recognize(self, audio_data):
        if not self.recognizer:
            return None
        try:
            return self.recognizer.recognize_sphinx(audio_data).lower()
        except:
            pass
        try:
            return self.recognizer.recognize_google(audio_data).lower()
        except Exception as e:
            logger.debug(f"SR recognition failed: {e}")
        return None


class AudioListener:
    def __init__(self, on_voice_callback=None):
        self.audio = CrossPlatformAudio()
        self.callback = on_voice_callback
        self.listening = False
        self.thread = None
    
    def start(self):
        if self.listening:
            return
        self.listening = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        logger.info("Audio listener started")
    
    def stop(self):
        self.listening = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Audio listener stopped")
    
    def _listen_loop(self):
        if not self.audio.recognizer or not self.audio.mic:
            logger.error("No speech recognizer available")
            return
        
        while self.listening:
            try:
                with self.audio.mic as source:
                    self.audio.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    while self.listening:
                        try:
                            audio = self.audio.recognizer.listen(source, timeout=1, phrase_time_limit=3)
                            text = self.audio.recognize_speech(audio)
                            
                            if text and self.callback:
                                self.callback(text)
                        except sr.WaitTimeoutError:
                            continue
                        except Exception as e:
                            logger.debug(f"Listen error: {e}")
            except Exception as e:
                logger.error(f"Microphone error: {e}")
                import time
                time.sleep(1)


class AudioPlayer:
    def __init__(self):
        self.sample_rate = 22050
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
    
    def play_audio(self, audio_data, sample_rate=None):
        if SD_AVAILABLE:
            try:
                sr = sample_rate or self.sample_rate
                if isinstance(audio_data, bytes):
                    audio_np = np.frombuffer(audio_data, dtype=np.int16)
                else:
                    audio_np = audio_data
                sd.play(audio_np, sr)
                sd.wait()
                return True
            except Exception as e:
                logger.error(f"Audio playback failed: {e}")
        return False
    
    def play_wav_file(self, filepath):
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


audio_service = None

def get_audio_service():
    global audio_service
    if audio_service is None:
        audio_service = CrossPlatformAudio()
    return audio_service
