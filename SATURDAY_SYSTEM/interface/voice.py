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
        """Arms the voice path (STT engines lazy-load inside ears on first use)."""
        logger.info("Voice engine initialized.")
        self.active = True

    def stop_listening(self):
        self.active = False
        logger.info("Voice engine suspended.")

    def process_voice_command(self, audio_data, language=None):
        """Real transcription: int16 samples or WAV path → whisper → core.
        Returns transcribed text (and the core result when a core is bound)."""
        from saturday import ears

        if isinstance(audio_data, str):
            res = ears.transcribe(wav_path=audio_data, language=language)
        else:
            res = ears.transcribe(samples=audio_data, language=language)
        transcription = (res.get("text", "") or "").strip()
        logger.info(f"Transcribed: {transcription}")
        if not transcription:
            return {"text": "", "result": "silence"}
        if self.core is None:
            return {"text": transcription, "result": None}
        return {"text": transcription,
                "result": self.core.process_command(transcription)}

    def speak(self, text: str, voice: str = ""):
        """Outputs text through local TTS engine (Piper, platform TTS, or pyttsx3 fallback)."""
        logger.info(f"SATURDAY Speaking: {text}")
        if not text:
            return
        try:
            from saturday import edgeglow as _eg
            _eg.signal("speaking", max(3.0, min(12.0, len(text) / 18.0)))
        except Exception:
            pass
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
            # 1b. Kokoro human-like neural voice (local ONNX, CPU).
            # Default when SATURDAY_TTS=kokoro|auto and weights are on D:.
            # Voice personas: SATURDAY=af_sarah, EDITH=af_nicole (override
            # via SATURDAY_KOKORO_VOICE / EDITH_KOKORO_VOICE).
            if os.getenv("SATURDAY_TTS", "kokoro").lower() in ("kokoro", "auto"):
                try:
                    from saturday import kokoro_voice as _kv
                    want = (voice or "").lower()
                    if "edith" in want or "nicole" in want or "female" in want:
                        kv_voice = os.getenv("EDITH_KOKORO_VOICE", "af_nicole")
                    elif "michael" in want or "male" in want:
                        kv_voice = os.getenv("SATURDAY_KOKORO_VOICE", "am_michael")
                    else:
                        kv_voice = os.getenv("SATURDAY_KOKORO_VOICE", "af_sarah")
                    wav = _kv.render_wav(text, voice=kv_voice)
                    if sys.platform.startswith("win"):
                        import winsound
                        winsound.PlaySound(wav, winsound.SND_FILENAME)
                        return
                    player = shutil.which("aplay") or shutil.which("afplay") or shutil.which("play")
                    if player:
                        subprocess.Popen([player, wav],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return
                except Exception as e:
                    logger.warning(f"Kokoro TTS unavailable, falling through: {e}")
            # 2. Piper neural voices when selected AND models configured.
            # Defaults (D:, offline, yours forever): SATURDAY = ryan (male),
            # EDITH = amy (female). `voice` picks the persona model.
            if os.getenv("SATURDAY_TTS", "piper").lower() in ("piper", "auto"):
                piper_bin = os.getenv("PIPER_BIN", "") or shutil.which("piper") or ""
                if not piper_bin:
                    for cand in (
                            r"D:\S.A.T.U.R.D.A.Y\models\piper\piper\piper.exe",
                            os.path.join(os.path.expanduser("~"), ".local", "bin", "piper")):
                        if os.path.exists(cand):
                            piper_bin = cand
                            break
                vdir = os.getenv("PIPER_VOICES_DIR", r"D:\S.A.T.U.R.D.A.Y\models\piper\voices")
                want = (voice or "").lower()
                length_scale = os.getenv("SATURDAY_PIPER_LENGTH", "1.0")
                sentence_silence = os.getenv("SATURDAY_PIPER_SILENCE", "0.3")
                if "amy" in want:
                    model = os.path.join(vdir, "en_US-amy-medium.onnx")
                elif "ryan" in want:
                    model = os.path.join(vdir, "en_US-ryan-medium.onnx")
                elif "joe" in want:
                    model = os.path.join(vdir, "en_US-joe-medium.onnx")
                    length_scale = os.getenv("SATURDAY_PIPER_LENGTH", "1.1")
                    sentence_silence = os.getenv("SATURDAY_PIPER_SILENCE", "0.5")
                elif "john" in want:
                    model = os.path.join(vdir, "en_US-john-medium.onnx")
                    length_scale = os.getenv("SATURDAY_PIPER_LENGTH", "1.1")
                    sentence_silence = os.getenv("SATURDAY_PIPER_SILENCE", "0.5")
                elif "kristin" in want:
                    model = os.path.join(vdir, "en_US-kristin-medium.onnx")
                    length_scale = os.getenv("EDITH_PIPER_LENGTH", length_scale)
                    sentence_silence = os.getenv("EDITH_PIPER_SILENCE", sentence_silence)
                elif "kathleen" in want:
                    model = os.path.join(vdir, "en_US-kathleen-low.onnx")
                    length_scale = os.getenv("EDITH_PIPER_LENGTH", length_scale)
                    sentence_silence = os.getenv("EDITH_PIPER_SILENCE", sentence_silence)
                elif "edith" in want or "zira" in want or "female" in want or "lessac" in want:
                    model = os.getenv("EDITH_PIPER_MODEL", os.path.join(vdir, "en_US-amy-medium.onnx"))
                    length_scale = os.getenv("EDITH_PIPER_LENGTH", "1.15")
                    sentence_silence = os.getenv("EDITH_PIPER_SILENCE", "0.6")
                else:
                    model = (os.getenv("PIPER_MODEL_PATH", "")
                             or os.getenv("SATURDAY_PIPER_MODEL", "")
                             or os.path.join(vdir, "en_US-joe-medium.onnx"))
                    if "SATURDAY_PIPER_LENGTH" not in os.environ:
                        length_scale = "1.1"
                    if "SATURDAY_PIPER_SILENCE" not in os.environ:
                        sentence_silence = "0.5"
                if piper_bin and model and os.path.exists(model):
                    tmp_wav = os.path.join(os.getenv("SATURDAY_D_TMP", r"D:\SATURDAY_TEMP"),
                                            "saturday_tts.wav")
                    cmd = [piper_bin, "--model", model, "--output_file", tmp_wav]
                    try:
                        ls = float(length_scale)
                        if abs(ls - 1.0) > 0.01:
                            cmd += ["--length-scale", str(ls)]
                    except Exception:
                        pass
                    try:
                        ss = float(sentence_silence)
                        if ss > 0.01:
                            cmd += ["--sentence-silence", str(ss)]
                    except Exception:
                        pass
                    subprocess.run(
                        cmd,
                        input=text, capture_output=True, text=True, check=True,
                        timeout=60,
                        cwd=os.path.dirname(piper_bin),
                    )
                    if sys.platform.startswith("win"):
                        import winsound

                        winsound.PlaySound(tmp_wav, winsound.SND_FILENAME)
                        return
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
                if self._windows_speak(text, voice=voice or os.getenv("SATURDAY_TTS_VOICE", "")):
                    return
            self._fallback_voice(text)
        except Exception as e:
            logger.warning(f"TTS failed, falling back: {e}")
            try:
                self._fallback_voice(text)
            except Exception:
                pass

    def _windows_speak(self, text: str, voice: str = "") -> bool:
        """Best-effort Windows speech via System.Speech; returns True on success.
        voice: substring of the SAPI voice name ('Zira' = female en-US)."""
        import os
        try:
            import subprocess
            volume = min(100, max(0, int(os.getenv("SATURDAY_TTS_VOLUME", "80"))))
            rate = min(10, max(-10, int(os.getenv("SATURDAY_TTS_RATE", "0"))))
            safe = text.replace("'", "''").replace('"', '""')[:1000]
            pick = ""
            if (voice or "").strip():
                hint = voice.replace("'", "''")
                pick = (f"$v=$s.GetInstalledVoices() | Where-Object {{$_.VoiceInfo.Name -like '*{hint}*'}} "
                        f"| Select-Object -First 1; if ($v) {{ $s.SelectVoice($v.VoiceInfo.Name) }}; ")
            ps = (
                "Add-Type -AssemblyName System.Speech; "
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"{pick}"
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
