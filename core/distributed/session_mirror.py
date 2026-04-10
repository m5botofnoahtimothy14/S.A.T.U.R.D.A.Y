                               
class SessionMirror:
    def __init__(self):
        self.session_state = {}

    def update(self, key, value):
        self.session_state[key] = value

    def snapshot(self):
        return self.session_state
