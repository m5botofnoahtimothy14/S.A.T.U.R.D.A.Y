                           
import logging
import random

logger = logging.getLogger("SATURDAY.ChristianityCore")

class ChristianityCore:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.scriptures = [
            "Proverbs 3:5-6: Trust in the LORD with all your heart...",
            "Matthew 5:16: Let your light shine before others...",
            "Philippians 4:13: I can do all things through Christ who strengthens me.",
            "Psalm 23:1: The Lord is my shepherd; I shall not want."
        ]
        self.event_bus.subscribe("voice_command", self.handle_query)

    def handle_query(self, command):
        cmd = command.lower()
        if "scripture" in cmd or "bible" in cmd:
            verse = random.choice(self.scriptures)
            logger.info(f"Serving scripture: {verse}")
            self.event_bus.publish("voice_response", verse)
            self.event_bus.publish("scripture_update", verse)
        elif "pray" in cmd:
            topics = ["peace", "guidance", "strength", "gratitude"]
            topic = random.choice(topics)
            prayer = self._generate_prayer(topic)
            self.event_bus.publish("voice_response", prayer)

    def _generate_prayer(self, topic):
        prayers = {
            "peace": "Dear Lord, grant me the peace that transcends all understanding to guard my heart and mind.",
            "guidance": "Father, lead me in the path of righteousness and give me wisdom for the decisions of this day.",
            "strength": "Lord, fill me with Your strength so that I may endure all things through Christ.",
            "gratitude": "Heavenly Father, I thank You for Your grace and the abundance of blessings in my life."
        }
        return prayers.get(topic, "Lord, be with me today. Amen.")

    def get_ethical_advice(self, query):
        q = query.lower()
        if any(w in q for w in ["lie", "deceit", "dishonest"]):
            return "Integrity is the foundation of character. Proverbs 10:9 says, 'Whoever walks in integrity walks securely.'"
        if any(w in q for w in ["angry", "mad", "hate"]):
            return "Patience and love are greater than wrath. Matthew 5:44 commands us to love even our enemies."
        if any(w in q for w in ["lazy", "give up", "tired"]):
            return "Diligent hands bring wealth. Colossians 3:23 reminds us to work with all our heart as if for the Lord."
            
        return "In all your ways acknowledge He, and He shall direct your paths with integrity and compassion."
