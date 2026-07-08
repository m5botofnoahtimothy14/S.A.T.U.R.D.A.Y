import logging
import os
import queue
import threading
import time
import tempfile
import asyncio

import numpy as np

try:
    import sounddevice as sd
except (ImportError, OSError):
    sd = None

logger = logging.getLogger("SATURDAY.Speech")

EDGE_TTS_AVAILABLE = False
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    pass

PIPER_AVAILABLE = False
try:
    from piper import PiperVoice
    PIPER_AVAILABLE = True
except ImportError:
    PiperVoice = None

SATURDAY_VOICE = os.getenv("SATURDAY_TTS_VOICE", "en-US-ChristopherNeural")
SATURDAY_VOICE_RATE = os.getenv("SATURDAY_TTS_RATE", "+0%")
SATURDAY_VOICE_PITCH = os.getenv("SATURDAY_TTS_PITCH", "+0Hz")


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

        if EDGE_TTS_AVAILABLE:
            self.backend = "edge-tts"
            self._speaker_thread = threading.Thread(target=self._speaker_loop, daemon=True)
            self._speaker_thread.start()
            logger.info(f"TTS backend: Edge TTS (voice={SATURDAY_VOICE})")
            return

        self._speaker_thread = threading.Thread(target=self._speaker_loop, daemon=True)
        self._speaker_thread.start()
        if sd:
            self.backend = "sounddevice"
            logger.info("TTS backend: SoundDevice (cross-platform)")
        else:
            self.backend = "none"
            logger.warning("No TTS backend available")

    def _init_piper(self):
        if not PIPER_AVAILABLE:
            return False
        model_path = os.getenv("PIPER_MODEL_PATH", "models/piper/en_US-lessac-medium.onnx")
        if not model_path or not os.path.exists(model_path):
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
        return self.piper_voice is not None or self.backend == "edge-tts" or sd is not None

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
                    elif self.backend == "edge-tts":
                        self._speak_edge(text)
                    else:
                        self._speak_fallback(text)
            except Exception as e:
                logger.warning(f"Speech error: {e}")

    def _speak_edge(self, text: str):
        try:
            tmp_path = os.path.join(tempfile.gettempdir(), "saturday_speech.mp3")
            communicate = edge_tts.Communicate(
                text,
                SATURDAY_VOICE,
                rate=SATURDAY_VOICE_RATE,
                pitch=SATURDAY_VOICE_PITCH,
            )
            asyncio.run(communicate.save(tmp_path))

            if os.path.exists(tmp_path) and sd:
                try:
                    import subprocess
                    wav_path = tmp_path.replace(".mp3", ".wav")
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", tmp_path, "-ar", "24000", "-ac", "1", wav_path],
                        capture_output=True,
                        timeout=10,
                    )
                    if os.path.exists(wav_path):
                        audio_data, sr = self._load_wav(wav_path)
                        sd.play(audio_data, sr)
                        sd.wait()
                        os.remove(wav_path)
                    else:
                        self._speak_fallback(text)
                except Exception:
                    self._speak_fallback(text)
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
            elif os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Edge TTS error: {e}")
            self._speak_fallback(text)

    def _speak_piper(self, text: str):
        if not self.piper_voice or not sd:
            self._speak_fallback(text)
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
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Piper error: {e}")
            self._speak_fallback(text)

    def _speak_fallback(self, text: str):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 155)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
            return
        except Exception:
            pass
        logger.info(f"TTS unavailable (text only): {text[:80]}...")

    def _load_wav(self, filepath: str):
        import wave
        with wave.open(filepath, "rb") as wf:
            sr = wf.getframerate()
            data = wf.readframes(-1)
            audio = np.frombuffer(data, dtype=np.int16)
            return audio, sr
