

import os
import numpy as np
import logging
import threading
import queue
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import struct

logger = logging.getLogger("AEGIS.OwnVoice")

try:
    import sounddevice as sd
    SD_AVAILABLE = True
except:
    SD_AVAILABLE = False


class VoiceStyle(Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    CALM = "calm"
    ANGRY = "angry"
    WHISPER = "whisper"
    THINKING = "thinking"


@dataclass
class VoiceConfig:
    sample_rate: int = 24000
    pitch_shift: float = 0.0
    speed: float = 1.0
    volume: float = 1.0
    style: VoiceStyle = VoiceStyle.NEUTRAL
    emotion_intensity: float = 0.5
    warmth: float = 0.7
    clarity: float = 0.8
    breathiness: float = 0.2


class NeuralVocoder:
    
    
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self._vocoder = None
        self._initialized = False
        self._lock = threading.Lock()
        
        self._init_vocoder()
    
    def _init_vocoder(self):
        
        try:
            import torch
            if torch.cuda.is_available():
                self._device = "cuda"
            else:
                self._device = "cpu"
            self._initialized = True
            logger.info(f"Neural vocoder initialized on {self._device}")
        except ImportError:
            logger.warning("PyTorch not available, using fallback vocoder")
            self._device = "cpu"
            self._initialized = True
        except Exception as e:
            logger.error(f"Vocoder init failed: {e}")
    
    def synthesize(self, mel_spectrogram: np.ndarray) -> np.ndarray:
        
        with self._lock:
            try:
                if self._vocoder:
                    return self._vocoder(mel_spectrogram)
                return self._fallback_synthesize(mel_spectrogram)
            except Exception as e:
                logger.error(f"Synthesis error: {e}")
                return self._fallback_synthesize(mel_spectrogram)
    
    def _fallback_synthesize(self, mel: np.ndarray) -> np.ndarray:
        
        try:
            from scipy.signal import istft
            
            mel_height, mel_width = mel.shape
            
            stft_matrix = np.exp(mel) * 0.1
            
            stft_matrix = np.pad(stft_matrix, ((0, 0), (0, 512 - mel_width % 512)), mode='constant')
            
            audio = istft(stft_matrix, fs=self.sample_rate, nperseg=1024, noverlap=512)
            
            return audio
            
        except Exception as e:
            logger.error(f"Fallback synthesis failed: {e}")
            return np.zeros(int(self.sample_rate * 0.1))


class TextToPhonemes:
    
    
    _phoneme_map = {
        'a': ['AA'], 'e': ['EH'], 'i': ['IH'], 'o': ['OW'], 'u': ['AH'],
        'b': ['B'], 'c': ['K'], 'd': ['D'], 'f': ['F'], 'g': ['G'],
        'h': ['HH'], 'j': ['JH'], 'k': ['K'], 'l': ['L'], 'm': ['M'],
        'n': ['N'], 'p': ['P'], 'q': ['K'], 'r': ['R'], 's': ['S'],
        't': ['T'], 'v': ['V'], 'w': ['W'], 'x': ['KS'], 'y': ['Y'], 'z': ['Z'],
        'th': ['DH'], 'sh': ['SH'], 'ch': ['CH'], 'ng': ['NG']
    }
    
    _durations = {
        'AA': 0.12, 'AE': 0.11, 'AH': 0.10, 'AO': 0.12, 'OW': 0.15,
        'EH': 0.09, 'ER': 0.11, 'IH': 0.08, 'IY': 0.10, 'UH': 0.09,
        'UW': 0.11, 'B': 0.08, 'CH': 0.10, 'D': 0.07, 'DH': 0.08,
        'F': 0.09, 'G': 0.08, 'HH': 0.06, 'JH': 0.11, 'K': 0.09,
        'L': 0.08, 'M': 0.08, 'N': 0.08, 'NG': 0.10, 'P': 0.08,
        'R': 0.09, 'S': 0.09, 'SH': 0.11, 'T': 0.07, 'TH': 0.08,
        'V': 0.08, 'W': 0.09, 'Y': 0.07, 'Z': 0.09, 'ZH': 0.10
    }
    
    def convert(self, text: str) -> List[Dict[str, Any]]:
        
        text = text.lower().strip()
        phonemes = []
        
        i = 0
        while i < len(text):
            if text[i] == ' ':
                i += 1
                continue
            
            two_char = text[i:i+2] if i + 1 < len(text) else ''
            
            if two_char in self._phoneme_map:
                ph = self._phoneme_map[two_char][0]
                phonemes.append({
                    'phoneme': ph,
                    'duration': self._durations.get(ph, 0.1),
                    'pitch': 1.0
                })
                i += 2
            elif text[i] in self._phoneme_map:
                ph = self._phoneme_map[text[i]][0]
                phonemes.append({
                    'phoneme': ph,
                    'duration': self._durations.get(ph, 0.1),
                    'pitch': 1.0
                })
                i += 1
            else:
                i += 1
        
        return phonemes


class MelSpectrogramGenerator:
    
    
    def __init__(self, sample_rate: int = 24000, n_mels: int = 80):
        self.sample_rate = sample_rate
        self.n_mels = n_mels
        self.n_fft = 2048
        self.hop_length = 256
        self.win_length = 1024
        
        self._mel_basis = self._create_mel_basis()
    
    def _create_mel_basis(self):
        
        try:
            from scipy.fft import fft
            from scipy.signal import get_window
            
            def hz_to_mel(hz):
                return 2595 * np.log10(1 + hz / 700)
            
            def mel_to_hz(mels):
                return 700 * (10 ** (mels / 2595) - 1)
            
            low_freq_mel = hz_to_mel(0)
            high_freq_mel = hz_to_mel(self.sample_rate / 2)
            
            mel_points = np.linspace(low_freq_mel, high_freq_mel, self.n_mels + 2)
            hz_points = mel_to_hz(mel_points)
            
            bin_points = np.floor((self.n_fft + 1) * hz_points / self.sample_rate).astype(int)
            
            mel_basis = np.zeros((self.n_mels, int(self.n_fft / 2 + 1)))
            
            for i in range(self.n_mels):
                left = bin_points[i]
                center = bin_points[i + 1]
                right = bin_points[i + 2]
                
                for j in range(left, center):
                    mel_basis[i, j] = (j - left) / (center - left)
                for j in range(center, right):
                    mel_basis[i, j] = (right - j) / (right - center)
            
            return mel_basis
            
        except Exception as e:
            logger.error(f"Mel basis creation failed: {e}")
            return np.random.randn(self.n_mels, int(self.n_fft / 2 + 1)) * 0.1
    
    def generate(self, phonemes: List[Dict], style: VoiceStyle = VoiceStyle.NEUTRAL,
                 emotion_intensity: float = 0.5) -> np.ndarray:
        
        
        frames = []
        base_freq = 120
        
        style_mods = {
            VoiceStyle.HAPPY: {'pitch_mult': 1.2, 'speed_mult': 1.1, 'energy_mult': 1.3},
            VoiceStyle.SAD: {'pitch_mult': 0.9, 'speed_mult': 0.8, 'energy_mult': 0.7},
            VoiceStyle.EXCITED: {'pitch_mult': 1.3, 'speed_mult': 1.2, 'energy_mult': 1.5},
            VoiceStyle.CALM: {'pitch_mult': 0.95, 'speed_mult': 0.9, 'energy_mult': 0.8},
            VoiceStyle.ANGRY: {'pitch_mult': 1.1, 'speed_mult': 1.15, 'energy_mult': 1.4},
            VoiceStyle.WHISPER: {'pitch_mult': 0.8, 'speed_mult': 0.85, 'energy_mult': 0.3},
            VoiceStyle.THINKING: {'pitch_mult': 0.97, 'speed_mult': 0.7, 'energy_mult': 0.6},
            VoiceStyle.NEUTRAL: {'pitch_mult': 1.0, 'speed_mult': 1.0, 'energy_mult': 1.0}
        }
        
        mods = style_mods.get(style, style_mods[VoiceStyle.NEUTRAL])
        pitch_mult = mods['pitch_mult'] * (1 + (emotion_intensity - 0.5) * 0.3)
        
        for ph in phonemes:
            duration_frames = int(ph['duration'] * self.sample_rate / self.hop_length * mods['speed_mult'])
            
            pitch = ph['pitch'] * pitch_mult
            
            frame = np.zeros((self.n_mels, max(1, duration_frames)))
            
            for i in range(frame.shape[1]):
                t = i / frame.shape[1]
                
                freq = base_freq * pitch * (1 + 0.3 * np.sin(2 * np.pi * 3 * t))
                
                for m in range(self.n_mels):
                    mel_freq = m * 50 + 100
                    frame[m, i] = np.exp(-((np.log(freq + 1) - np.log(mel_freq + 1)) ** 2) / 0.5)
                
                energy = mods['energy_mult'] * (1 - 0.3 * t)
                frame[:, i] *= energy
            
            frames.append(frame)
        
        if not frames:
            return np.zeros((self.n_mels, 100))
        
        mel = np.concatenate(frames, axis=1)
        
        mel = np.log(np.clip(mel, 1e-5, None) + 0.1)
        
        return mel.astype(np.float32)


class HumanVoiceSynthesizer:
    
    
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self.config = VoiceConfig(sample_rate=sample_rate)
        
        self._phoneme_converter = TextToPhonemes()
        self._mel_generator = MelSpectrogramGenerator(sample_rate)
        self._vocoder = NeuralVocoder(sample_rate)
        
        self._audio_queue = queue.Queue(maxsize=5)
        self._synthesis_thread = None
        self._is_synthesizing = False
        
        self._pitch_profile = self._create_pitch_profile()
        self._prosody_model = self._create_prosody_model()
        
        logger.info("AEGIS Own Voice synthesizer initialized")
    
    def _create_pitch_profile(self) -> Dict:
        
        return {
            'base': 150,
            'range': 50,
            'contour_smoothness': 0.7,
            'emphasis_freq': 0.3,
            'pause_duration': 0.15
        }
    
    def _create_prosody_model(self) -> Dict:
        
        return {
            'syllable_rate': 4.0,
            'word_pause': 0.1,
            'sentence_pause': 0.3,
            'question_rise': 0.2,
            'emphasis_scale': 1.3
        }
    
    def speak(self, text: str, style: VoiceStyle = VoiceStyle.NEUTRAL,
              emotion_intensity: float = 0.5) -> np.ndarray:
        
        
        phonemes = self._phoneme_converter.convert(text)
        
        if not phonemes:
            return np.zeros(int(self.sample_rate * 0.5))
        
        for ph in phonemes:
            ph['pitch'] = self._apply_prosody(ph, style)
        
        mel = self._mel_generator.generate(phonemes, style, emotion_intensity)
        
        audio = self._vocoder.synthesize(mel)
        
        audio = self._post_process(audio)
        
        audio = self._apply_emotion(audio, style, emotion_intensity)
        
        return audio
    
    def _apply_prosody(self, phoneme: Dict, style: VoiceStyle) -> float:
        
        base = 1.0
        
        import random
        variation = random.uniform(-0.1, 0.1)
        
        if style == VoiceStyle.EXCITED:
            base *= 1.2
        elif style == VoiceStyle.SAD:
            base *= 0.9
        elif style == VoiceStyle.THINKING:
            base *= 0.95
        
        return base + variation
    
    def _post_process(self, audio: np.ndarray) -> np.ndarray:
        
        
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        if self.config.volume != 1.0:
            audio *= self.config.volume
        
        if self.config.speed != 1.0:
            import scipy.signal as signal
            audio = signal.resample(audio, int(len(audio) / self.config.speed))
        
        if self.config.pitch_shift != 0:
            semitones = self.config.pitch_shift
            speed_factor = 2 ** (semitones / 12)
            audio = scipy.signal.resample(audio, int(len(audio) / speed_factor))
        
        fade_samples = int(self.sample_rate * 0.02)
        audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
        audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)
        
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * 0.95
        
        return audio
    
    def _apply_emotion(self, audio: np.ndarray, style: VoiceStyle, 
                      intensity: float) -> np.ndarray:
        
        
        if style == VoiceStyle.WHISPER:
            noise = np.random.randn(len(audio)) * 0.1 * intensity
            audio = audio * (1 - intensity * 0.5) + noise * intensity
        
        elif style == VoiceStyle.HAPPY or style == VoiceStyle.EXCITED:
            import scipy.signal as signal
            b, a = signal.butter(2, [100, 3000], btype='bandpass', fs=self.sample_rate)
            filtered = signal.filtfilt(b, a, audio)
            audio = audio * (1 - intensity * 0.3) + filtered * intensity * 0.3
        
        elif style == VoiceStyle.SAD:
            audio = audio * (1 - intensity * 0.2)
        
        elif style == VoiceStyle.THINKING:
            pause_samples = int(self.sample_rate * 0.05)
            pauses = np.zeros(len(audio))
            segment = len(audio) // 10
            for i in range(10):
                pos = i * segment + segment // 2
                pauses[pos:pos + pause_samples] = 1
            audio = audio * (1 - pauses * intensity * 0.3)
        
        return audio
    
    def speak_async(self, text: str, style: VoiceStyle = VoiceStyle.NEUTRAL,
                   emotion_intensity: float = 0.5, callback=None):
        
        def synthesize():
            audio = self.speak(text, style, emotion_intensity)
            self._audio_queue.put((audio, callback))
        
        thread = threading.Thread(target=synthesize, daemon=True)
        thread.start()
    
    def get_next_audio(self, timeout: float = None) -> Optional[np.ndarray]:
        
        try:
            audio, callback = self._audio_queue.get(timeout=timeout)
            if callback:
                callback(audio)
            return audio
        except queue.Empty:
            return None


class AEGISVoice:
    
    
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
        self.synthesizer = HumanVoiceSynthesizer(sample_rate=24000)
        
        self._speaker = None
        if SD_AVAILABLE:
            try:
                from core.audio_speaker import get_default_speaker
                self._speaker = get_default_speaker()
            except:
                pass
        
        self._current_style = VoiceStyle.NEUTRAL
        self._emotion_intensity = 0.5
        
        logger.info("AEGIS Own Voice activated")
    
    def speak(self, text: str, style: VoiceStyle = None, emotion: float = None):
        
        if style is None:
            style = self._current_style
        if emotion is None:
            emotion = self._emotion_intensity
        
        audio = self.synthesizer.speak(text, style, emotion)
        
        if self._speaker:
            self._speaker.play(audio, wait=True)
        else:
            self._play_fallback(audio)
    
    def speak_async(self, text: str, style: VoiceStyle = None, emotion: float = None):
        
        def _speak():
            self.speak(text, style, emotion)
        
        thread = threading.Thread(target=_speak, daemon=True)
        thread.start()
    
    def _play_fallback(self, audio: np.ndarray):
        
        try:
            import wave
            import tempfile
            import os
            
            audio_int16 = (audio * 32767).astype(np.int16)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
                with wave.open(f.name, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(audio_int16.tobytes())
                
                temp_path = f.name
            
            import subprocess
            subprocess.Popen(['powershell', '-c', f'(New-Object System.Media.SoundPlayer "{temp_path}").PlaySync()'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            try:
                os.remove(temp_path)
            except:
                pass
                
        except Exception as e:
            logger.error(f"Fallback playback failed: {e}")
    
    def set_style(self, style: VoiceStyle):
        
        self._current_style = style
        logger.info(f"Voice style set to: {style.value}")
    
    def set_emotion(self, intensity: float):
        
        self._emotion_intensity = max(0.0, min(1.0, intensity))
    
    def respond(self, text: str):
        
        
        if '?' in text:
            self.speak(text, VoiceStyle.CALM, 0.4)
        elif any(word in text.lower() for word in ['great', 'awesome', 'excellent', 'amazing']):
            self.speak(text, VoiceStyle.HAPPY, 0.6)
        elif any(word in text.lower() for word in ['sorry', 'unfortunately', 'sad']):
            self.speak(text, VoiceStyle.SAD, 0.5)
        elif any(word in text.lower() for word in ['wow', 'incredible', 'unbelievable']):
            self.speak(text, VoiceStyle.EXCITED, 0.7)
        elif any(word in text.lower() for word in ['let me think', 'hmm', 'considering']):
            self.speak(text, VoiceStyle.THINKING, 0.5)
        else:
            self.speak(text, VoiceStyle.NEUTRAL, 0.5)


def get_aegis_voice() -> AEGISVoice:
    
    return AEGISVoice()
