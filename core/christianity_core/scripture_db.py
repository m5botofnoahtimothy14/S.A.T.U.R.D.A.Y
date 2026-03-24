# scripture_db.py

import random


class ScriptureDB:

    def __init__(self):
        self.scriptures = [
            {
                "ref": "Proverbs 4:7",
                "text": "Wisdom is the principal thing; therefore get wisdom."
            },
            {
                "ref": "James 1:5",
                "text": "If any of you lacks wisdom, ask God."
            },
            {
                "ref": "Philippians 4:13",
                "text": "I can do all things through Him who strengthens me."
            },
            {
                "ref": "Colossians 3:23",
                "text": "Whatever you do, work at it with all your heart."
            }
        ]

    def get_random(self) -> dict:
        return random.choice(self.scriptures)

    def search(self, keyword: str) -> list:
        keyword = keyword.lower()
        return [
            verse for verse in self.scriptures
            if keyword in verse["text"].lower()
        ]
