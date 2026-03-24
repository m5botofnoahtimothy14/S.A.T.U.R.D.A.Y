# auto_reply_engine.py

from .sentiment_engine import SentimentEngine


class AutoReplyEngine:

    def __init__(self):
        self.sentiment = SentimentEngine()

    def generate_reply(self, message: str) -> str:

        analysis = self.sentiment.analyze(message)
        mood = analysis["mood"]

        if mood == "positive":
            return "Glad to hear that. Let’s keep the momentum strong."

        if mood == "negative":
            return "I understand. Let’s address this calmly and find a solution."

        return "Understood. Give me more details so we can move efficiently."
