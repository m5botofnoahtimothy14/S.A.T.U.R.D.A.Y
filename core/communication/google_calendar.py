import structlog
import os
import json
from datetime import datetime, timedelta
from core.event_bus import EventBus

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    Credentials = None
    InstalledAppFlow = None
    build = None
    HttpError = None

logger = structlog.get_logger("SATURDAY.Communication.Calendar")

SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
]
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", 'data/google_token.json')
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", 'data/google_credentials.json')

class CalendarManager:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.event_bus.subscribe("check_calendar", self.fetch_events)
        self.event_bus.subscribe("check_email", self.fetch_emails)
        self.service = None
        self.gmail_service = None
        self._authenticate()

    def _authenticate(self):
        os.makedirs('data', exist_ok=True)
        
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r", encoding="utf-8") as handle:
                    creds = Credentials.from_authorized_user_info(json.load(handle), SCOPES)
                self._build_services(creds)
                logger.info("Google services loaded from token")
                return
            except Exception as e:
                logger.warning(f"Token load failed: {e}")
        
        if not os.path.exists(CREDENTIALS_FILE):
            logger.error("Google credentials file missing", path=CREDENTIALS_FILE)
            return

        if self._credentials_placeholder():
            logger.error("Google credentials file still contains placeholder values", path=CREDENTIALS_FILE)
            return
        
        try:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, 'w') as f:
                json.dump(json.loads(creds.to_json()), f)
            self._build_services(creds)
            logger.info("Google authentication complete")
        except Exception as e:
            logger.error(f"Google auth failed: {e}")

    def _credentials_placeholder(self) -> bool:
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return True
        serialized = json.dumps(payload)
        return "YOUR_CLIENT_ID" in serialized or "YOUR_SECRET" in serialized

    def _build_services(self, creds):
        try:
            self.service = build('calendar', 'v3', credentials=creds)
            self.gmail_service = build('gmail', 'v1', credentials=creds)
        except Exception as e:
            logger.error(f"Service build failed: {e}")

    async def fetch_events(self, data: dict = None):
        logger.info("Fetching calendar events...")
        
        if not self.service:
            logger.error("Calendar API requested but Google Calendar is not configured")
            return []

        try:
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = self.service.events().list(
                calendarId='primary', timeMin=now,
                maxResults=10, singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                msg = f"Event: {event['summary']} at {start}"
                self.event_bus.publish("voice_response", msg)
            
            return events
        except HttpError as e:
            logger.error(f"Calendar API error: {e}")
            return []

    async def fetch_emails(self, data: dict = None):
        logger.info("Fetching recent emails...")
        
        if not self.gmail_service:
            logger.error("Gmail API requested but Google Gmail is not configured")
            return []

        try:
            results = self.gmail_service.users().messages().list(
                userId='me', maxResults=5
            ).execute()
            messages = results.get('messages', [])
            
            for msg_id in messages:
                msg = self.gmail_service.users().messages().get(
                    userId='me', id=msg_id['id']
                ).execute()
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                from_addr = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                self.event_bus.publish("voice_response", f"Email from {from_addr}: {subject}")
            
            return messages
        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            return []

    async def send_email(self, to: str, subject: str, body: str):
        from email.mime.text import MIMEText
        import base64
        
        if not self.gmail_service:
            logger.error("Send email requested but Gmail is not configured")
            return False

        try:
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            self.gmail_service.users().messages().send(
                userId='me', body={'raw': encoded}
            ).execute()
            return True
        except HttpError as e:
            logger.error(f"Send email error: {e}")
            return False
