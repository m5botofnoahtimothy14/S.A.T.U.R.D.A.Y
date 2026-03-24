# notification_router.py

class NotificationRouter:

    def __init__(self):
        self.routes = {}

    def register_route(self, source, handler):
        self.routes[source] = handler

    async def route(self, source, payload):
        if source in self.routes:
            await self.routes[source](payload)
        else:
            print(f"[NotificationRouter] No handler for {source}")
