# communication/livekit_webhooks.py
import uuid
import structlog
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

logger = structlog.get_logger("AEGIS.LiveKitWebhooks")


def register_livekit_webhooks(app, call_agent, event_bus):
    """
    Mount LiveKit-compatible endpoints for SIP telephony:
    - POST /api/livekit/webhook : Receive room events (SIP participants joining)
    - POST /api/livekit/outbound : Trigger outbound call
    - POST /api/livekit/meeting  : Join a meeting (Zoom, Meet, etc.)
    """
    router = APIRouter()

    @router.post("/api/livekit/webhook")
    async def livekit_webhook(request: Request):
        """
        Handle LiveKit room events, particularly SIP participant events.
        When a SIP caller joins, we route them through the AI agent.
        """
        body = await request.body()
        # In production, verify the webhook signature
        # For now, parse the event type from the body
        
        # LiveKit sends webhook events as JSON
        try:
            import json
            event_data = json.loads(body)
            event_type = event_data.get("event")
            
            if event_type == "sip_participant_joined":
                participant = event_data.get("participant", {})
                identity = participant.get("identity", "")
                call_sid = event_data.get("room", {}).get("sid", call_agent.build_session_id())
                
                logger.info("SIP participant joined", identity=identity, room_sid=call_sid)
                
                # Ensure session and greet the caller
                session = call_agent.ensure_session(call_sid, identity)
                greeting = call_agent.greeting_text(session)
                
                # Publish event to start the voice agent for this caller
                event_bus.publish("sip_call_started", {
                    "call_sid": call_sid,
                    "caller": identity,
                    "room_sid": event_data.get("room", {}).get("sid"),
                })
                
                # For LiveKit, the agent handles greeting via the room audio
                return JSONResponse({"status": "greeting", "message": greeting})
            
            elif event_type == "sip_participant_left":
                participant = event_data.get("participant", {})
                identity = participant.get("identity", "")
                logger.info("SIP participant left", identity=identity)
                
                event_bus.publish("sip_call_ended", {
                    "caller": identity,
                })
                return JSONResponse({"status": "ok"})
                
        except Exception as e:
            logger.warning("Failed to parse LiveKit webhook", error=str(e))
        
        return JSONResponse({"status": "ignored"})

    @router.post("/api/livekit/outbound")
    async def livekit_outbound(data: dict):
        """
        Trigger an outbound phone call via LiveKit SIP.
        """
        to = data.get("to")
        script = data.get("script", "Hi, this is AEGIS calling.")
        
        if not to:
            raise HTTPException(status_code=400, detail="Missing 'to' phone number")
        
        if not call_agent.outbound_supported():
            raise HTTPException(status_code=400, detail="LiveKit SIP not configured. Check SIP_OUTBOUND_TRUNK_ID")
        
        try:
            result = await call_agent.create_outbound_call(to)
            session_id = call_agent.build_session_id()
            call_agent.ensure_session(session_id, to)
            call_agent.sessions[session_id]["one_shot_script"] = script
            
            logger.info("Outbound call initiated", to=to, result=result)
            return JSONResponse({"status": "initiated", "call": result, "session_id": session_id})
        except Exception as e:
            logger.error("Failed to place outbound call", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/livekit/meeting")
    async def livekit_meeting(data: dict):
        """
        Dial into a meeting (Zoom, Google Meet, etc.) via SIP.
        """
        dial_in = data.get("dial_in")
        meeting_id = data.get("meeting_id")
        passcode = data.get("passcode")
        
        if not (dial_in and meeting_id):
            raise HTTPException(status_code=400, detail="dial_in and meeting_id are required")
        
        if not call_agent.outbound_supported():
            raise HTTPException(status_code=400, detail="LiveKit SIP not configured")
        
        try:
            result = await call_agent.dial_meeting(dial_in, meeting_id, passcode)
            logger.info("Meeting dial initiated", dial_in=dial_in, meeting_id=meeting_id)
            return JSONResponse({"status": "dialing", "meeting": result})
        except Exception as e:
            logger.error("Failed to dial meeting", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/livekit/status")
    async def livekit_status():
        """Check LiveKit SIP status."""
        return JSONResponse({
            "sip_available": call_agent.outbound_supported(),
            "livekit_url": call_agent.livekit_url,
            "has_trunk": bool(call_agent.sip_outbound_trunk_id),
        })

    app.include_router(router)
    logger.info("LiveKit webhooks registered")
