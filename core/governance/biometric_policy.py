                                
class BiometricPolicy:
    def __init__(self):
        self.allowed_users = set()

    def register_user(self, user_id):
        self.allowed_users.add(user_id)

    def is_allowed(self, user_id):
        return user_id in self.allowed_users
