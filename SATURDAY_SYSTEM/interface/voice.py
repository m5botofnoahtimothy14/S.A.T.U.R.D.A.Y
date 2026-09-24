import logging

logger = logging.getLogger("SATURDAY.Voice")

class SATURDAYVoice:
    """
    SATURDAY Voice Interface Module.
    This serves as a bridge for STT (Speech-to-Text) and TTS (Text-to-Speech) engines.
    """
    def __init__(self, core):
        self.core = core
        self.active = False

    def start_listening(self):
        """
        In a full implementation, this would initialize a microphone 
        and run a local STT engine (like Whisper.cpp or Vosk).
        """
        logger.info("Voice engine initialized. (Simulated)")
        self.active = True

    def stop_listening(self):
        self.active = False
        logger.info("Voice engine suspended.")

    def process_voice_command(self, audio_data):
        """Processes audio and passes transcribed text to SATURDAY core."""
        # Simulated transcription
        transcription = "status"
        logger.info(f"Transcribed: {transcription}")
        return self.core.process_command(transcription)

    def speak(self, text: str):
        """Outputs text through local TTS engine (Piper, platform TTS, or pyttsx3 fallback)."""
        logger.info(f"SATURDAY Speaking: {text}")
        if not text:
            return
        try:
            import os
            import shutil
            import subprocess
            import sys
            import tempfile
            # 1. Custom CLI override wins when explicitly configured.
            tts_cli = os.getenv("SATURDAY_TTS_CLI", "")
            if tts_cli:
                cli_path = shutil.which(tts_cli) or (tts_cli if os.path.exists(tts_cli) else None)
                if cli_path:
                    subprocess.run([cli_path, text], check=True)
                    return
            # 2. Piper when selected AND a valid model is configured.
            if os.getenv("SATURDAY_TTS", "auto").lower() in ("piper", "auto"):
                piper = shutil.which("piper")
                model = os.getenv("PIPER_MODEL_PATH", "")
                if piper and model and os.path.exists(model):
                    tmp_wav = os.path.join(tempfile.gettempdir(), "saturday_tts.wav")
                    subprocess.run(
                        ["piper", "--model", model, "--output_file", tmp_wav],
                        input=text, capture_output=True, text=True, check=True,
                    )
                    player = shutil.which("aplay") or shutil.which("afplay") or shutil.which("play")
                    if player:
                        subprocess.Popen([player, tmp_wav],
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
                        return
            # 3. Platform text-to-speech
            if sys.platform == "darwin":
                subprocess.Popen(["say", text],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            elif sys.platform.startswith("win"):
                if self._windows_speak(text):
                    return
            self._fallback_voice(text)
        except Exception as e:
            logger.warning(f"TTS failed, falling back: {e}")
            try:
                self._fallback_voice(text)
            except Exception:
                pass

    def _windows_speak(self, text: str) -> bool:
        """Best-effort Windows speech via System.Speech; returns True on success."""
        import os
        try:
            import subprocess
            volume = min(100, max(0, int(os.getenv("SATURDAY_TTS_VOLUME", "80"))))
            rate = min(10, max(-10, int(os.getenv("SATURDAY_TTS_RATE", "0"))))
            safe = text.replace("'", "''").replace('"', '""')[:1000]
            ps = (
                "Add-Type -AssemblyName System.Speech; "
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Volume={volume}; $s.Rate={rate}; "
                f"$s.Speak('{safe}')"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=30)
            return True
        except Exception as e:
            logger.debug(f"Windows SAPI speech unavailable: {e}")
            return False

    def _fallback_voice(self, text: str):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.warning(f"No local TTS engine available: {e}")
