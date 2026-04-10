                                  
from typing import Optional
import uuid
import structlog
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

logger = structlog.get_logger("AEGIS.Twilio")

def register_twilio_webhooks(app, call_agent):
    
    router = APIRouter()

    @router.post("/api/voice/inbound")
    async def voice_inbound(request: Request):
        form = await request.form()
        call_sid = form.get("CallSid") or call_agent.build_session_id()
        caller = form.get("From")
        session = call_agent.ensure_session(call_sid, caller)

        action_url = _build_action_url(request, f"/api/voice/inbound/gather?sid={call_sid}")
        prompt = call_agent.greeting_text(session)
        twiml = call_agent.build_twiml_gather(prompt, action_url)
        return PlainTextResponse(twiml, media_type="text/xml")

    @router.post("/api/voice/inbound/gather")
    async def voice_inbound_gather(request: Request):
        form = await request.form()
        call_sid = form.get("CallSid") or request.query_params.get("sid") or call_agent.build_session_id()
        speech_result = form.get("SpeechResult") or form.get("TranscriptionText") or ""
        logger.info("Inbound speech result", sid=call_sid, text=speech_result)

        reply = await call_agent.handle_user_text(call_sid, speech_result)
        action_url = _build_action_url(request, f"/api/voice/inbound/gather?sid={call_sid}")
        twiml = call_agent.build_twiml_gather(reply, action_url)
        return PlainTextResponse(twiml, media_type="text/xml")

    @router.post("/api/voice/outbound")
    async def voice_outbound(data: dict):
        to = data.get("to")
        script = data.get("script", "Hi, this is AEGIS following up on your request.")
        if not to:
            raise HTTPException(status_code=400, detail="Missing 'to'")
        if not call_agent.outbound_supported():
            raise HTTPException(status_code=400, detail="Twilio not configured for outbound calls")

        base_url = call_agent.public_base_url
        if not base_url:
            raise HTTPException(status_code=400, detail="PUBLIC_BASE_URL env var required for outbound calls")
        session_id = call_agent.build_session_id()
        call_agent.ensure_session(session_id, to)
                                                         
        twiml_url = f"{base_url}/api/voice/outbound/script/{session_id}"
        result = call_agent.create_outbound_call(to, twiml_url)
                                                             
        call_agent.sessions[session_id]["one_shot_script"] = script
        return JSONResponse(result)

    @router.post("/api/voice/meeting/join")
    async def meeting_join(data: dict):
        dial_in = data.get("dial_in")
        meeting_id = data.get("meeting_id")
        passcode = data.get("passcode")
        if not (dial_in and meeting_id):
            raise HTTPException(status_code=400, detail="dial_in and meeting_id are required")
        if not call_agent.outbound_supported():
            raise HTTPException(status_code=400, detail="Twilio not configured for outbound calls")

        base_url = call_agent.public_base_url
        if not base_url:
            raise HTTPException(status_code=400, detail="PUBLIC_BASE_URL env var required for outbound calls")

        session_id = call_agent.build_session_id()
        call_agent.ensure_session(session_id, dial_in)
        call_agent.sessions[session_id]["meeting_twiml"] = call_agent.build_meeting_twiml(
            dial_in, meeting_id, passcode
        )
        twiml_url = f"{base_url}/api/voice/meeting/script/{session_id}"
        result = call_agent.create_outbound_call(dial_in, twiml_url)
        return JSONResponse({"call": result, "session": session_id})

    @router.api_route("/api/voice/outbound/script/{session_id}", methods=["GET", "POST"])
    async def voice_outbound_script(session_id: str):
        session = call_agent.sessions.get(session_id) or call_agent.ensure_session(session_id, None)
        script = session.get("one_shot_script") or "This is AEGIS. How can I help you today?"
                                                                          
        action_url = f"/api/voice/inbound/gather?sid={session_id}"
        twiml = call_agent.build_twiml_gather(script, action_url)
        return PlainTextResponse(twiml, media_type="text/xml")

    @router.api_route("/api/voice/meeting/script/{session_id}", methods=["GET", "POST"])
    async def voice_meeting_script(session_id: str):
        session = call_agent.sessions.get(session_id)
        if not session or "meeting_twiml" not in session:
            raise HTTPException(status_code=404, detail="Unknown meeting session")
        return PlainTextResponse(session["meeting_twiml"], media_type="text/xml")

    app.include_router(router)
    logger.info("Twilio webhooks registered")

def _build_action_url(request: Request, path: str) -> str:
                                                                                       
    if hasattr(request.app, "aegis") and request.app.aegis.call_agent.public_base_url:
        base = request.app.aegis.call_agent.public_base_url.rstrip("/")
        return f"{base}{path}"
    url = str(request.base_url).rstrip("/")
    return f"{url}{path}"
