                             
import asyncio
import datetime
import json
import os
import uuid
from pathlib import Path
from typing import Optional

import structlog
from livekit import api

logger = structlog.get_logger("AEGIS.CallAgent")

def _load_json(path, default=None):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
    except Exception as e:
        logger.warning("CallAgent failed to load JSON", path=path, error=str(e))
    return default if default is not None else []

def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return path

class CallAgent:
    
    def __init__(
        self,
        event_bus,
        llm_engine,
        directory_file: str = "data/directory.json",
        default_locale: str = "en-US",
    ):
        self.event_bus = event_bus
        self.llm = llm_engine
        self.directory_file = directory_file
        self.default_locale = default_locale
        self.sessions = {}
        self.log_dir = _ensure_dir(Path("logs") / "calls")

        self.livekit_url = os.getenv("LIVEKIT_URL")
        self.livekit_api_key = os.getenv("LIVEKIT_API_KEY")
        self.livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")
        self.sip_outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")
        self.public_base_url = os.getenv("PUBLIC_BASE_URL")

        self._lk_api: Optional[api.LiveKitAPI] = None
        self._sip_available = False

        if all([self.livekit_url, self.livekit_api_key, self.livekit_api_secret]):
            try:
                self._lk_api = api.LiveKitAPI(
                    url=self.livekit_url,
                    api_key=self.livekit_api_key,
                    api_secret=self.livekit_api_secret,
                )
                self._sip_available = True
                logger.info("LiveKit SIP initialized successfully")
            except Exception as e:
                logger.warning("Failed to initialize LiveKit API", error=str(e))
        else:
            logger.warning("LiveKit credentials incomplete. SIP calls disabled.")

    def ensure_session(self, call_sid: str, caller: str | None) -> dict:
        if call_sid in self.sessions:
            return self.sessions[call_sid]

        contacts = _load_json(self.directory_file, [])
        contact_name = None
        for contact in contacts:
            if caller and caller.endswith(contact.get("phone", "")):
                contact_name = contact.get("name")
                break

        session = {
            "id": call_sid,
            "caller": caller or "unknown",
            "contact_name": contact_name,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "transcript": [],
            "state": "greeting",
        }
        self.sessions[call_sid] = session
        logger.info("New call session", call_sid=call_sid, caller=caller)
        return session

    def _log_line(self, call_sid: str, role: str, text: str):
        ts = datetime.datetime.utcnow().isoformat()
        line = f"{ts} [{role.upper()}] {text}\n"
        session = self.sessions.get(call_sid)
        if session is not None:
            session["transcript"].append({"t": ts, "role": role, "text": text})
        with open(self.log_dir / f"{call_sid}.log", "a", encoding="utf-8") as handle:
            handle.write(line)

    def greeting_text(self, session: dict) -> str:
        if session.get("contact_name"):
            return f"Hi {session['contact_name']}, this is AEGIS. How can I help you today?"
        return "Hi, you've reached AEGIS, the autonomous assistant. How can I help?"

    async def generate_reply(self, call_sid: str, user_text: str) -> str:
        prompt = (
            "You are AEGIS, a concise and capable voice agent. "
            "Goals: understand the caller's intent, confirm key details (time, date, people, numbers), "
            "offer to act, and close clearly. "
            "Style: brief, warm, no jargon. "
            "Always propose a next action or summary before ending. "
            f'Caller said: "{user_text}".'
        )

        if not self.llm:
            reply = "I cannot continue this call because the language model backend is unavailable."
            self._log_line(call_sid, "assistant", reply)
            return reply

        reply = ""
        try:
            async for chunk in self.llm.chat_stream(prompt):
                reply += chunk
        except Exception as e:
            logger.warning("LLM error in call agent", error=str(e))
            reply = "I cannot continue this call because the language model backend failed."

        self._log_line(call_sid, "assistant", reply)
        return reply

    async def handle_user_text(self, call_sid: str, text: str) -> str:
        session = self.sessions.get(call_sid) or self.ensure_session(call_sid, None)
        self._log_line(call_sid, "user", text or "<silence>")
        session["state"] = "in_call"
        return await self.generate_reply(call_sid, text or "")

    def outbound_supported(self) -> bool:
        return self._sip_available and bool(self.sip_outbound_trunk_id)

    async def create_outbound_call(self, to_number: str, room_name: str = None) -> dict:
        if not self.outbound_supported():
            raise RuntimeError("LiveKit SIP not configured for outbound calls. Check SIP_OUTBOUND_TRUNK_ID.")

        if not self._lk_api:
            raise RuntimeError("LiveKit API not initialized.")

        room_name = room_name or f"outbound-{uuid.uuid4().hex[:8]}"
        call_sid = uuid.uuid4().hex

        try:
            participant = await self._lk_api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=self.sip_outbound_trunk_id,
                    sip_call_to=to_number,
                    room_name=room_name,
                    participant_identity=f"caller_{call_sid[:8]}",
                    krisp_enabled=True,
                    wait_until_answered=True,
                )
            )
            logger.info(
                "Outbound call initiated via LiveKit SIP",
                to=to_number,
                room=room_name,
                participant_id=participant.participant_id,
            )
            return {
                "sid": call_sid,
                "room_name": room_name,
                "to": to_number,
                "status": "initiated",
                "participant_id": participant.participant_id,
            }
        except Exception as e:
            logger.error("Failed to create outbound call", error=str(e))
            raise RuntimeError(f"Failed to place call: {e}") from e

    async def dial_meeting(self, dial_in_number: str, meeting_id: str, passcode: str = None) -> dict:
        if not self.outbound_supported():
            raise RuntimeError("LiveKit SIP not configured for meeting dial-in.")

        digits = f"ww{meeting_id}#"
        if passcode:
            digits += f"ww{passcode}#"

        room_name = f"meeting-{uuid.uuid4().hex[:8]}"

        try:
            participant = await self._lk_api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=self.sip_outbound_trunk_id,
                    sip_call_to=dial_in_number,
                    room_name=room_name,
                    participant_identity="meeting_bridge",
                    dtmf=digits,
                    krisp_enabled=True,
                    wait_until_answered=True,
                )
            )
            logger.info("Meeting dial-in initiated", number=dial_in_number, meeting_id=meeting_id, room=room_name)
            return {
                "room_name": room_name,
                "status": "dialing",
                "meeting_id": meeting_id,
                "participant_id": participant.participant_id,
            }
        except Exception as e:
            logger.error("Failed to dial meeting", error=str(e))
            raise RuntimeError(f"Failed to dial meeting: {e}") from e

    def build_twiml_gather(self, prompt_text: str, action_url: str, end_on_silence=5):
        logger.debug("TwiML gather not needed with LiveKit - uses WebRTC directly")
        return "<!-- LiveKit handles speech via WebRTC -->"

    def build_twiml_say(self, text: str):
        logger.debug("TwiML say not needed with LiveKit - uses WebRTC directly")
        return "<!-- LiveKit handles TTS directly -->"

    def build_meeting_twiml(self, dial_in_number: str, meeting_id: str, passcode: str = None):
        logger.warning("build_meeting_twiml is deprecated, use dial_meeting() async method")
        return {"dial_in_number": dial_in_number, "meeting_id": meeting_id, "passcode": passcode}

    async def close(self):
        if self._lk_api:
            await self._lk_api.aclose()

    def build_session_id(self):
        return uuid.uuid4().hex
