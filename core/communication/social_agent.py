# communication/social_agent.py
import logging
import asyncio
import email
import imaplib
import os
import time
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.Social")

class SocialAgent:
    """Handles Gmail, Calendar, and social DM automation."""
    def __init__(self, event_bus: EventBus, human_interface):
        self.event_bus = event_bus
        self.hi = human_interface
        self.idle_mode = False
        self.last_alerts = []
        self.last_schedule = []
        self.email_user = os.getenv("EMAIL_USER1", "").strip()
        self.email_pass = os.getenv("EMAIL_PASS1", "").strip()
        self.imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com").strip()
        self.calendar_ics_url = os.getenv("AEGIS_CALENDAR_ICS_URL", "").strip()
        self.calendar_ics_path = os.getenv("AEGIS_CALENDAR_ICS_PATH", "").strip()
        
        # Subscribe to system state
        self.event_bus.subscribe("power_mode", self._on_power_mode)
        logger.info("Social Agent initialized.")

    def _on_power_mode(self, data):
        self.idle_mode = (data.get("mode") == "low")

    async def check_schedules(self):
        """Return real schedule data from an ICS source when configured."""
        if not self.calendar_ics_url and not self.calendar_ics_path:
            return []

        loop = asyncio.get_running_loop()
        self.last_schedule = await loop.run_in_executor(None, self._load_ics_schedule)
        return self.last_schedule

    async def sync_social_dms(self):
        """Return only real alerts. Social DM polling is disabled until a provider is configured."""
        self.last_alerts = []
        return self.last_alerts

    async def check_email_status(self):
        if not self.email_user or not self.email_pass:
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_unread_emails)

    async def start_monitoring(self):
        """Background loop for social syncing."""
        logger.info("Social monitoring background task started.")
        while True:
            try:
                schedules = await self.check_schedules()
                emails = await self.check_email_status()
                dms = await self.sync_social_dms()
                alerts = emails + dms
                self.last_alerts = alerts

                if schedules and not self.idle_mode:
                    next_item = schedules[0]
                    logger.info("Upcoming schedule item", item=next_item)

                if alerts and not self.idle_mode:
                    first = alerts[0]
                    self.event_bus.publish("voice_response", f"New {first['source']} activity from {first['from']}.")
            except Exception as e:
                logger.warning(f"Social monitoring error: {e}")
            await asyncio.sleep(300) # Every 5 minutes

    def get_summary(self):
        return {
            "alerts": self.last_alerts,
            "schedule": self.last_schedule,
            "idle_mode": self.idle_mode,
            "timestamp": time.time()
        }

    def _fetch_unread_emails(self):
        alerts = []
        try:
            with imaplib.IMAP4_SSL(self.imap_server) as mailbox:
                mailbox.login(self.email_user, self.email_pass)
                mailbox.select("INBOX")
                status, data = mailbox.search(None, "UNSEEN")
                if status != "OK":
                    return alerts
                for mail_id in data[0].split()[:5]:
                    status, msg_data = mailbox.fetch(mail_id, "(RFC822)")
                    if status != "OK" or not msg_data:
                        continue
                    raw_email = msg_data[0][1]
                    message = email.message_from_bytes(raw_email)
                    subject = message.get("Subject", "(No subject)")
                    sender = message.get("From", "Unknown sender")
                    alerts.append({
                        "source": "Email",
                        "from": sender,
                        "text": subject,
                        "time": time.time(),
                    })
        except Exception as e:
            logger.warning("Email polling failed: %s", e)
        return alerts

    def _load_ics_schedule(self):
        raw_text = ""
        if self.calendar_ics_url:
            try:
                import requests
                response = requests.get(self.calendar_ics_url, timeout=6)
                response.raise_for_status()
                raw_text = response.text
            except Exception as e:
                logger.warning("Calendar ICS download failed: %s", e)
        elif self.calendar_ics_path and os.path.exists(self.calendar_ics_path):
            with open(self.calendar_ics_path, "r", encoding="utf-8", errors="ignore") as handle:
                raw_text = handle.read()

        events = []
        current = {}
        for line in raw_text.splitlines():
            line = line.strip()
            if line == "BEGIN:VEVENT":
                current = {}
            elif line == "END:VEVENT":
                if current:
                    events.append(current)
                current = {}
            elif ":" in line:
                key, value = line.split(":", 1)
                current[key] = value
        normalized = []
        for item in events[:10]:
            normalized.append({
                "time": item.get("DTSTART", ""),
                "task": item.get("SUMMARY", "Untitled event"),
            })
        return normalized
