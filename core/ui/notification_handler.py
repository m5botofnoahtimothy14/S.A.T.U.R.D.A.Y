                            
import threading
import time
try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

class NotificationHandler:
    def __init__(self):
        pass

    def notify(self, title, message, duration=5):
        threading.Thread(target=self._notify_thread, args=(title, message, duration), daemon=True).start()

    def _notify_thread(self, title, message, duration):
        if not PLYER_AVAILABLE:
            return
        notification.notify(
            title=title,
            message=message,
            timeout=duration
        )
