import os

import structlog

logger = structlog.get_logger("SATURDAY.LiveKit")

class LiveKitBridge:
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.url = os.getenv("LIVEKIT_URL", "").strip()
        self.api_key = os.getenv("LIVEKIT_API_KEY", "").strip()
        self.api_secret = os.getenv("LIVEKIT_API_SECRET", "").strip()
        self.room_name = os.getenv("LIVEKIT_ROOM", "saturday-session").strip()
        self.identity = os.getenv("LIVEKIT_IDENTITY", "saturday-core").strip()
        self.participant_name = os.getenv("LIVEKIT_PARTICIPANT_NAME", "SATURDAY Core").strip()

        self.room = None
        self.active = False
        self._sdk_available = False
        self._connect_error = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._reconnect_delay = 5

        try:
            from livekit import api, rtc

            self.api = api
            self.rtc = rtc
            self._sdk_available = True
        except ImportError as e:
            self._connect_error = f"LiveKit SDK not installed: {e}"
            logger.error(self._connect_error)

        self.event_bus.subscribe("voice_response", self._handle_voice_response)
        self.event_bus.subscribe("camera_frame", self._handle_camera_frame)
        logger.info("LiveKit Bridge initialized.", configured=self.configured, sdk_available=self._sdk_available)

    @property
    def configured(self) -> bool:
        return all([self.url, self.api_key, self.api_secret, self.room_name])

    async def _handle_voice_response(self, text: str):
        if not self.active or not self.room or not text:
            return
        try:
            await self.room.local_participant.publish_data(str(text), reliable=True, topic="voice_response")
        except Exception as e:
            logger.error("Failed to publish voice response to LiveKit", error=str(e))

    async def _handle_camera_frame(self, frame_data):
        if not self.active or not self.room or not frame_data:
            return
        try:
            await self.room.local_participant.publish_data(frame_data if isinstance(frame_data, bytes) else str(frame_data), reliable=False, topic="camera_frame")
        except Exception as e:
            logger.error("Failed to publish camera frame to LiveKit", error=str(e))

    async def start(self):
        if not self._sdk_available:
            logger.error("LiveKit start skipped because SDK is unavailable.")
            return
        if not self.configured:
            logger.error("LiveKit credentials are incomplete; bridge cannot connect.")
            return

        try:
            token = (
                self.api.AccessToken(self.api_key, self.api_secret)
                .with_identity(self.identity)
                .with_name(self.participant_name)
                .with_grants(
                    self.api.VideoGrants(
                        room_join=True,
                        room=self.room_name,
                        can_publish=True,
                        can_subscribe=True,
                        can_publish_data=True,
                    )
                )
                .to_jwt()
            )

            self.room = self.rtc.Room()
            
            @self.room.event_handler("disconnected")
            async def on_disconnected():
                self.active = False
                if self._reconnect_attempts < self._max_reconnect_attempts:
                    self._reconnect_attempts += 1
                    logger.warning(f"LiveKit disconnected, reconnecting in {self._reconnect_delay}s (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})")
                    import asyncio
                    await asyncio.sleep(self._reconnect_delay)
                    await self.start()
                else:
                    logger.error("LiveKit max reconnection attempts reached")
            
            await self.room.connect(self.url, token, timeout=30)
            self.active = True
            self._connect_error = None
            self._reconnect_attempts = 0
            logger.info("Connected to LiveKit room", room=self.room_name, identity=self.identity)
        except Exception as e:
            self._connect_error = str(e)
            self.active = False
            logger.error("Failed to connect to LiveKit", error=str(e))

    async def stop(self):
        if self.room:
            try:
                await self.room.disconnect()
            except Exception as e:
                logger.warning("LiveKit disconnect failed", error=str(e))
        self.active = False
