import asyncio
import json
import os
import structlog
from typing import Optional

logger = structlog.get_logger("AEGIS.Sync")

class StateSyncNode:
    """
    AEGIS Synchronization Node.
    Synchronizes state and events across multiple AEGIS instances using Redis.
    Phase F: Distributed state management.
    """
    def __init__(self, event_bus, runtime_stats):
        self.event_bus = event_bus
        self.runtime = runtime_stats
        self.active = False
        self.connected = False
        self.redis = None
        
        try:
            import redis.asyncio as redis
            self.redis_cli = redis
            self.active = True
        except ImportError:
            logger.warning("redis-py not found. Sync Node disabled.")
            
        logger.info("Sync Node module initialized.", active=self.active)

    async def _handle_remote_event(self, channel, message):
        """Receive state/events from a remote AEGIS instance."""
        try:
            data = json.loads(message)
            logger.debug(f"Received sync data from channel {channel}", data=data)
            # Re-publish to local event bus if necessary
            # self.event_bus.publish("sync_event", data)
        except Exception as e:
            logger.error("Sync error parsing message", error=str(e))

    async def start(self):
        """Main loop for publishing state and subscribing to remote updates."""
        if not self.active: return
        
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            logger.info(f"Connecting Sync Node to Redis: {redis_url}")
            
            self.redis = self.redis_cli.from_url(redis_url)
            await self.redis.ping()
            self.connected = True
            pubsub = self.redis.pubsub()
            await pubsub.subscribe("aegis:commands", "aegis:state")
            
            # Start a sub-task for listening
            asyncio.create_task(self._listen_loop(pubsub))
            
            # Main snapshot loop
            while True:
                if self.runtime:
                    snapshot = self.runtime.get_resource_usage()
                    await self.redis.publish("aegis:state", json.dumps(snapshot))
                
                await asyncio.sleep(10) # Publish state snapshot every 10 seconds
                
        except Exception as e:
            logger.error("Sync Node disconnected.", error=str(e))
            self.active = False
            self.connected = False

    async def _listen_loop(self, pubsub):
        """Background loop to process subscribed Redis channels."""
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    await self._handle_remote_event(message['channel'], message['data'])
        except Exception as e:
            logger.error("Sync Node listener loop crashed", error=str(e))
