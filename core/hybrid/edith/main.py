                      
import logging
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.EDITH")

class EDITH:
    def __init__(self, event_bus: EventBus, brain=None):
        self.event_bus = event_bus
        self.brain = brain
        self.active = False
        self._social = None
        
        self.event_bus.subscribe("voice_command", self._on_command)
        logger.info("EDITH (Stark Interface) initialized.")
    
    @property
    def social(self):
        if self._social is None:
            try:
                from .social_handler import EdithSocialHandler
                self._social = EdithSocialHandler(self.event_bus)
            except Exception as e:
                logger.warning(f"Social handler not available: {e}")
                self._social = None
        return self._social

    def _on_command(self, command):
        command = command.lower()
        if "edith" in command:
            self.active = True
            logger.info("EDITH Subdomain Interface active.")
            
            if "doctor" in command:
                if self.brain: self.brain.set_sub_mode("Doctor")
                self.event_bus.publish("voice_response", "EDITH Doctor Mode active. Medical sensors online.")
            elif "travel" in command or "travelling" in command:
                if self.brain: self.brain.set_sub_mode("Traveling")
                self.event_bus.publish("voice_response", "EDITH Travel Mode engaged. Monitoring transit.")
            elif "public" in command:
                if self.brain: self.brain.set_sub_mode("Public")
                self.event_bus.publish("voice_response", "EDITH Public Mode active. Privacy filters applied.")
            else:
                if self.brain: self.brain.set_sub_mode("Normal")
                self.event_bus.publish("voice_response", "EDITH online. How can I assist you?")
                
        elif "aegis" in command:
            self.active = False
            if self.brain:
                self.brain.set_sub_mode("Normal")                       
                self.brain.context["interface_mode"] = "AEGIS"
            self.event_bus.publish("voice_response", "AEGIS Core re-engaged. Welcome back, Sir.")

    def process_tactical_request(self, command):
        if "status" in command:
            self.event_bus.publish("voice_response", "All systems nominal. Security perimeter secure.")
        elif "deploy" in command:
             self.event_bus.publish("voice_response", "Tactical assets ready for deployment.")
        else:
            self.event_bus.publish("voice_response", "Input received. Analyzing.")
