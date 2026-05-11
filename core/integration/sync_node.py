import asyncio
import json
import os
import structlog
from typing import Optional

logger = structlog.get_logger("SATURDAY.Sync")

class StateSyncNode:
    
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
        
        try:
            data = json.loads(message)
            logger.debug(f"Received sync data from channel {channel}", data=data)
                                                        
        except Exception as e:
            logger.error("Sync error parsing message", error=str(e))

    async def start(self):
        
        if not self.active: return
        
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            logger.info(f"Connecting Sync Node to Redis: {redis_url}")
            
            self.redis = self.redis_cli.from_url(redis_url)
            await self.redis.ping()
            self.connected = True
            pubsub = self.redis.pubsub()
            await pubsub.subscribe("saturday:commands", "saturday:state")
            
            asyncio.create_task(self._listen_loop(pubsub))
            
            while True:
                if self.runtime:
                    snapshot = self.runtime.get_resource_usage()
                    await self.redis.publish("saturday:state", json.dumps(snapshot))
                
                await asyncio.sleep(10)                                          
                
        except Exception as e:
            logger.error("Sync Node disconnected.", error=str(e))
            self.active = False
            self.connected = False

    async def _listen_loop(self, pubsub):
        
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    await self._handle_remote_event(message['channel'], message['data'])
        except Exception as e:
            logger.error("Sync Node listener loop crashed", error=str(e))
