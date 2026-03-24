# governance/consent_manager.py
class ConsentManager:
    def __init__(self):
        self.consent_log = {}

    def give_consent(self, user, scope):
        self.consent_log.setdefault(user, set()).add(scope)

    def has_consent(self, user, scope):
        return scope in self.consent_log.get(user, set())
