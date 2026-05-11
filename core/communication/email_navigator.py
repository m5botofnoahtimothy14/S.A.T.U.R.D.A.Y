                                  
import structlog
import smtplib
from email.mime.text import MIMEText
from core.event_bus import EventBus
import os
import itertools

logger = structlog.get_logger("SATURDAY.Communication.Email")

class EmailNavigator:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.accounts = self._load_accounts()
        self.account_cycle = itertools.cycle(self.accounts) if self.accounts else None
        self.event_bus.subscribe("send_email", self.send_email)

    def _load_accounts(self):
        accounts = []
        for i in range(1, 4):
            user = os.getenv(f"EMAIL_USER{i}")
            password = os.getenv(f"EMAIL_PASS{i}")
            if user and password:
                accounts.append((user, password))
        if not accounts:
            logger.warning("No email accounts configured in env")
        else:
            logger.info("Loaded email accounts", count=len(accounts))
        return accounts

    async def send_email(self, data: dict):
        recipient = data.get("to")
        subject = data.get("subject", "SATURDAY Notification")
        body = data.get("body", "")

        if not self.account_cycle:
            logger.error("Email credentials missing in .env")
            self.event_bus.publish("voice_response", "Error: Email credentials missing.")
            return

        last_error = None
        sent = False

        for _ in range(len(self.accounts)):
            user, password = next(self.account_cycle)
            logger.info("Sending email", to=recipient, subject=subject, using=user)
            try:
                msg = MIMEText(body)
                msg['Subject'] = subject
                msg['From'] = user
                msg['To'] = recipient

                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(user, password)
                    server.send_message(msg)

                logger.info("Email sent successfully", to=recipient, using=user)
                self.event_bus.publish("voice_response", f"Email sent successfully to {recipient}.")
                sent = True
                break
            except Exception as e:
                last_error = str(e)
                logger.warning("Email send failed with account; trying next", error=last_error, account=user)
                continue

        if not sent:
            logger.error("Failed to send email with all configured accounts", error=last_error)
            self.event_bus.publish("voice_response", f"Failed to send email: {last_error}")
