try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

import threading
import structlog
import os
import time
import numpy as np
from core.event_bus import EventBus
from core.audio_service import CrossPlatformAudio

try:
    import sounddevice as sd
except ImportError:
    sd = None

logger = structlog.get_logger("SATURDAY.VoiceInterface")

SATURDAY_VOICE_RATE = 155
SATURDAY_VOICE_VOLUME = 1.0


class VoiceInterface:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.wake_word = "saturday"
        self.audio = CrossPlatformAudio()
        self.failure_streak = 0
        self.listening = True

        self._init_tts()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _init_tts(self):
        try:
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty("voices")
            male_voice = None
            for v in voices:
                name_lower = v.name.lower()
                if "male" in name_lower or "david" in name_lower or "mark" in name_lower:
                    male_voice = v
                    break
            if male_voice:
                self.engine.setProperty("voice", male_voice.id)
            self.engine.setProperty("rate", SATURDAY_VOICE_RATE)
            self.engine.setProperty("volume", SATURDAY_VOICE_VOLUME)
            logger.info(f"TTS initialized: {getattr(male_voice, 'name', 'default')}")
        except Exception as e:
            self.engine = None
            logger.warning("pyttsx3 unavailable, using SpeechManager", error=str(e))

    def _pick_input_device(self, rate):
        if sd is None:
            return None, rate
        try:
            hosts = sd.query_hostapis()
            devices = sd.query_devices()
        except Exception:
            return None, rate
        # Host enums observed on this machine: MME=0, DirectSound=1, WASAPI=2, WDM-KS=3.
        # WDM-KS native-opens crash the process; WASAPI-default (device 12) rejects 16k.
        # Prefer MME / DirectSound (safe, open 16k) and pick a real microphone.
        def host_idx(i):
            try:
                return int(devices[i]["hostapi"])
            except Exception:
                return -1
        def supports_input(i):
            try:
                return int(devices[i]["max_input_channels"] or 0) > 0
            except Exception:
                return False
        def is_mic(i):
            n = (devices[i].get("name") or "").lower()
            return any(k in n for k in ("microphone", "mic", "array", "front", "rear", "input"))
        def is_loopback(i):
            n = (devices[i].get("name") or "").lower()
            return "stereo mix" in n or "what u heard" in n or "loopback" in n
        def host_safe(i):
            h = host_idx(i)
            # 0=MME, 1=DirectSound are safe; WASAPI ok for input; WDM-KS is crash-prone
            return h >= 0
        candidates = [i for i in range(len(devices)) if supports_input(i) and host_safe(i) and not is_loopback(i)]
        # rank: real mic on MME/DS first, then WASAPI mic, then any safe input
        def rank(i):
            h = host_idx(i)
            return (0 if (h == 0 or h == 1) else 1, 0 if is_mic(i) else 1, i)
        candidates.sort(key=rank)
        if not candidates:
            logger.info("No microphone available; voice interface in output-only mode")
            return None, rate
        candidate = candidates[0]
        info = devices[candidate]
        max_in = int(info["default_samplerate"] or rate)
        return candidate, max_in if max_in >= 8000 else rate

    def _listen_loop(self):
        if sd is None:
            logger.warning("sounddevice unavailable, voice interface in output-only mode")
            return

        rate = 16000
        chunk_space = 20
        silence_budget = 8
        max_utterance_ms = 5000
        # float32 audio: RMS ranges roughly 0.0..0.5. Absolute 300 was int16-era and
        # never triggered -> no speech was ever recognized. Use a modest float floor
        # plus an adaptive noise floor so quiet mics still trigger reliably.
        noise_floor = 0.0005
        base_vad_threshold = 0.02
        vad_threshold = base_vad_threshold
        detected = False
        utterance = np.zeros(0, dtype=np.float32)
        silent_chunks = 0
        frame = 0

        while self.listening:
            try:
                device_idx, dev_rate = self._pick_input_device(rate)
                if device_idx is None:
                    logger.info("No microphone available, voice interface in output-only mode")
                    return

                logger.info(f"[Voice] capturing via sounddevice device {device_idx} @{dev_rate}")
                with sd.InputStream(device=device_idx, samplerate=dev_rate, channels=1, dtype="float32") as stream:
                    while self.listening:
                        block, _ = stream.read(chunk_space)
                        energy = float(np.sqrt(np.mean(np.square(block))))
                        # adaptive noise floor: exponential average during quiet frames
                        if not detected and energy < noise_floor:
                            noise_floor = 0.7 * noise_floor + 0.3 * energy
                            vad_threshold = max(base_vad_threshold, noise_floor * 4.0)
                        frame += 1
                        if energy > vad_threshold and not detected:
                            detected = True
                            utterance = np.array(block, dtype=np.float32)
                            silent_chunks = 0
                        elif detected:
                            utterance = np.concatenate([utterance, np.array(block, dtype=np.float32)])
                            if energy < vad_threshold:
                                silent_chunks += 1
                            else:
                                silent_chunks = 0
                            if (silent_chunks >= silence_budget) or (utterance.size / rate * 1000 >= max_utterance_ms):
                                detected = False
                                try:
                                    text = self.audio.recognize_speech(utterance)
                                except Exception as e:
                                    logger.warning(f"Voice recognition error: {e}")
                                    text = ""

                                utterance = np.zeros(0, dtype=np.float32)
                                silent_chunks = 0

                                if not text:
                                    self.failure_streak += 1
                                    continue

                                self.failure_streak = 0
                                text_lower = text.lower().strip()

                                if self.wake_word in text_lower:
                                    command = text_lower.replace(self.wake_word, "").strip()
                                    if command:
                                        self.event_bus.publish("voice_command", {"command": command})
                                    else:
                                        self.event_bus.publish("voice_command", {"command": "saturday"})
                                else:
                                    self.event_bus.publish("voice_command", {"command": text_lower})

            except Exception as e:
                logger.warning(f"Voice listener error: {e}")
                time.sleep(1)

    def speak(self, text: str):
        if not text:
            return
        if self.engine:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                logger.warning(f"pyttsx3 speak error: {e}")
        else:
            self.event_bus.publish("voice_response", text)

    def stop(self):
        self.listening = False
