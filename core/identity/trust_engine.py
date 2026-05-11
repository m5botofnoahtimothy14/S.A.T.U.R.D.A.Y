                          
import logging

logger = logging.getLogger("SATURDAY.Identity.Trust")

class TrustEngine:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.trust_levels = {}                          
        self.event_bus.subscribe("auth_success", self.increase_trust)
        self.event_bus.subscribe("auth_failure", self.decrease_trust)

    def increase_trust(self, user_id):
        score = self.trust_levels.get(user_id, 0.5)
        self.trust_levels[user_id] = min(1.0, score + 0.05)
        logger.info(f"Trust increased for {user_id}: {self.trust_levels[user_id]}")

    def decrease_trust(self, user_id):
        score = self.trust_levels.get(user_id, 0.5)
        self.trust_levels[user_id] = max(0.0, score - 0.1)
        logger.warning(f"Trust decreased for {user_id}: {self.trust_levels[user_id]}")
        if self.trust_levels[user_id] < 0.2:
            self.event_bus.publish("security_alert", {"reason": "Low trust score", "user": user_id})
