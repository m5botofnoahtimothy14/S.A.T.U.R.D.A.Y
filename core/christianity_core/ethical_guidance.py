# ethical_guidance.py

from datetime import datetime


class EthicalGuidanceEngine:
    """
    Ethical oversight and value-alignment module.
    Evaluates intents and returns advisory responses.
    """

    def __init__(self):
        self.restricted_keywords = [
            "harm",
            "attack",
            "exploit",
            "illegal",
            "hack",
            "destroy"
        ]

    def evaluate_intent(self, text: str) -> dict:
        text_lower = text.lower()

        for word in self.restricted_keywords:
            if word in text_lower:
                return {
                    "allowed": False,
                    "message": "This action conflicts with ethical alignment protocols."
                }

        return {
            "allowed": True,
            "message": "Intent ethically cleared."
        }

    def generate_reflection(self) -> str:
        hour = datetime.now().hour

        if hour < 12:
            return "Begin your day with integrity and disciplined intention."
        elif hour < 18:
            return "Act with precision and responsibility in all decisions."
        else:
            return "Reflect. Refine. Recalibrate."
