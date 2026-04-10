                            
import threading
import time
from plyer import notification

class NotificationHandler:
    def __init__(self):
        pass

    def notify(self, title, message, duration=5):
        threading.Thread(target=self._notify_thread, args=(title, message, duration), daemon=True).start()

    def _notify_thread(self, title, message, duration):
        notification.notify(
            title=title,
            message=message,
            timeout=duration
        )
