import logging
import os
import queue
import threading
import time
import tempfile

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

logger = logging.getLogger("SATURDAY.Speech")

PIPER_AVAILABLE = False
try:
    from piper import PiperVoice
    PIPER_AVAILABLE = True
except ImportError:
    PiperVoice = None


class SpeechManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.piper_voice = None
        self.backend = None
        self._queue = queue.Queue()
        self._speaker_thread = None
        self._init_backend()

    def _init_backend(self):
        self._init_piper()
        if self.piper_voice:
            self.backend = "piper"
            self._speaker_thread = threading.Thread(target=self._speaker_loop, daemon=True)
            self._speaker_thread.start()
            logger.info("TTS backend: Piper (DL)")
            return
        
        self._speaker_thread = threading.Thread(target=self._speaker_loop, daemon=True)
        self._speaker_thread.start()
        self.backend = "windows_waveout"
        logger.info("TTS backend: Windows WaveOut")

    def _init_piper(self):
        if not PIPER_AVAILABLE:
            return False
        model_path = os.getenv("PIPER_MODEL_PATH", "models/piper/en_US-lessac-medium.onnx")
        if not os.path.exists(model_path):
            logger.warning(f"Piper model not found: {model_path}")
            return False
        try:
            config_path = model_path.replace(".onnx", ".onnx.json")
            if not os.path.exists(config_path):
                config_path = model_path.replace(".onnx", ".json")
            self.piper_voice = PiperVoice.load(model_path, config_path=config_path)
            logger.info(f"Piper loaded: {model_path}")
            return True
        except Exception as e:
            logger.error(f"Piper init failed: {e}")
            return False

    @property
    def available(self) -> bool:
        return self.piper_voice is not None or sd is not None

    def speak(self, text: str, lang_hint: str = None):
        if not text:
            return
        if self._queue.qsize() > 10:
            return
        self._queue.put((text, lang_hint))

    def _speaker_loop(self):
        while True:
            try:
                text, lang_hint = self._queue.get()
                with self._lock:
                    if self.backend == "piper" and self.piper_voice:
                        self._speak_piper(text)
                    else:
                        self._speak_windows_wav(text)
            except Exception as e:
                logger.warning(f"Speech error: {e}")

    def _speak_piper(self, text: str):
        if not self.piper_voice or not sd:
            self._speak_windows_wav(text)
            return
        try:
            wav_path = os.path.join(tempfile.gettempdir(), "saturday_piper.wav")
            self.piper_voice.synthesize_wav(text, wav_path)
            
            if os.path.exists(wav_path):
                audio_data, sr = self._load_wav(wav_path)
                sd.play(audio_data, sr)
                sd.wait()
                try:
                    os.remove(wav_path)
                except:
                    pass
        except AttributeError as e:
            if "audio" in str(e).lower() or "AudioChunk" in str(e):
                try:
                    wav_path = os.path.join(tempfile.gettempdir(), "saturday_piper.wav")
                    import subprocess
                    result = subprocess.run([
                        "python", "-m", "piper", "--model", 
                        os.getenv("PIPER_MODEL_PATH", "models/piper/en_US-lessac-medium.onnx"),
                        "--output_file", wav_path
                    ], input=text, capture_output=True, text=True)
                    if os.path.exists(wav_path):
                        audio_data, sr = self._load_wav(wav_path)
                        sd.play(audio_data, sr)
                        sd.wait()
                        try:
                            os.remove(wav_path)
                        except:
                            pass
                    else:
                        self._speak_windows_wav(text)
                except Exception:
                    self._speak_windows_wav(text)
            else:
                logger.error(f"Piper error: {e}")
                self._speak_windows_wav(text)
        except Exception as e:
            logger.error(f"Piper error: {e}")
            self._speak_windows_wav(text)

    def _speak_windows_wav(self, text: str):
        try:
            import pythoncom
            import win32com.client
            
            pythoncom.CoInitialize()
            try:
                engine = win32com.client.Dispatch("SAPI.SpVoice")
                temp_wav = os.path.join(tempfile.gettempdir(), "saturday_temp.wav")
                fs = win32com.client.Dispatch("SAPI.SpFileStream")
                fs.Open(temp_wav, 3)
                engine.AudioOutputStream = fs
                engine.Speak(text)
                fs.Close()
                
                if os.path.exists(temp_wav) and sd:
                    audio_data, sr = self._load_wav(temp_wav)
                    sd.play(audio_data, sr)
                    sd.wait()
                    try:
                        os.remove(temp_wav)
                    except:
                        pass
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            logger.error(f"Windows TTS error: {e}")

    def _load_wav(self, filepath: str):
        import wave
        with wave.open(filepath, 'rb') as wf:
            sr = wf.getframerate()
            data = wf.readframes(-1)
            audio = np.frombuffer(data, dtype=np.int16)
            return audio, sr
