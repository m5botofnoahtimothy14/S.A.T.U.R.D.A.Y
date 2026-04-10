                     
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

class SentimentEngine:

    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()

    def analyze(self, text: str) -> dict:
        scores = self.analyzer.polarity_scores(text)

        compound = scores["compound"]

        if compound >= 0.5:
            mood = "positive"
        elif compound <= -0.5:
            mood = "negative"
        else:
            mood = "neutral"

        return {
            "mood": mood,
            "scores": scores
        }
