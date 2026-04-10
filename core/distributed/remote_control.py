                               
class RemoteControl:
    def __init__(self, rbac, event_bus):
        self.rbac = rbac
        self.event_bus = event_bus

    def execute_remote(self, user, command):
        if not self.rbac.can_execute("remote_control"):
            return False
        self.event_bus.publish("voice_command", command)
        return True
