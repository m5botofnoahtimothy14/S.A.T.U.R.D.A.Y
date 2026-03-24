# ui/edith_voice.py
import pyttsx3
import threading

class EdithVoice:
    def __init__(self):
        self.engine = pyttsx3.init()
        self._configure_voice()

    def _configure_voice(self):
        voices = self.engine.getProperty('voices')
        for v in voices:
            if "female" in v.name.lower():
                self.engine.setProperty('voice', v.id)
                break
        self.engine.setProperty('rate', 170)
        self.engine.setProperty('volume', 1.0)

    def speak(self, text: str):
        threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()

    def _speak_thread(self, text):
        self.engine.say(text)
        self.engine.runAndWait()
