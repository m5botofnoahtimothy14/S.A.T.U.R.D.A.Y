# prayer_reminder.py

import asyncio
from datetime import datetime


class PrayerReminder:

    def __init__(self, event_bus):
        self.event_bus = event_bus

        # Example fixed times (customize later)
        self.prayer_times = [
            "05:00",
            "12:00",
            "18:00",
            "21:00"
        ]

    async def monitor(self):
        while True:
            now = datetime.now().strftime("%H:%M")

            if now in self.prayer_times:
                self.event_bus.publish(
                    "prayer_time",
                    {"time": now}
                )

                await asyncio.sleep(60)  # Prevent duplicate trigger

            await asyncio.sleep(30)
