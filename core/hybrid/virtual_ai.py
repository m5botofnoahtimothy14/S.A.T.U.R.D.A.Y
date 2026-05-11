                      
import logging
from core.event_bus import EventBus

logger = logging.getLogger("SATURDAY.Hybrid.VirtualAI")

class VirtualAI:
    def __init__(self, event_bus: EventBus, llm_engine=None):
        self.event_bus = event_bus
        self.llm = llm_engine
        logger.info("Hybrid Virtual AI initialized.")

    async def get_response(self, prompt: str):
                                                 
        logger.info(f"Processing hybrid prompt: {prompt}")
        
        if self.llm:
            try:
                                                                                      
                response_text = ""
                async for chunk in self.llm.chat_stream(prompt):
                    response_text += chunk
                return response_text
            except Exception as e:
                logger.error(f"Local AI failed in Hybrid mode: {e}")
        
        return "I apologize, but my core intelligence is currently offline and I cannot provide a response."
