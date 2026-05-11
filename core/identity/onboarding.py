                        
import logging
from typing import Dict, Any
from core.event_bus import EventBus
from .database import SessionLocal, UserProfile

logger = logging.getLogger("SATURDAY.Identity.Onboarding")

class OnboardingManager:
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.pending_onboarding = {}

    async def initiate_onboarding(self, username: str) -> str:
        
        logger.info(f"Initiating onboarding for user: {username}")
        self.pending_onboarding[username] = {
            "status": "started",
            "steps_completed": [],
            "data": {}
        }
        
        self.event_bus.publish("onboarding_started", {"username": username})
        return f"Welcome {username}. Let's begin the SATURDAY initialization sequence."

    async def collect_user_info(self, username: str, info: Dict[str, Any]):
        
        if username not in self.pending_onboarding:
            return "User not found in onboarding queue."
            
        self.pending_onboarding[username]["data"].update(info)
        logger.info(f"Data collected for {username}: {list(info.keys())}")
        return "Information recorded."

    async def finalize_onboarding(self, username: str):
        
        if username not in self.pending_onboarding:
            return "Onboarding session not found."

        data = self.pending_onboarding[username]["data"]
        
        try:
            db = SessionLocal()
            new_user = UserProfile(
                username=username,
                trust_score=1.0                       
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            db.close()
            
            del self.pending_onboarding[username]
            logger.info(f"Onboarding finalized for {username}")
            
            self.event_bus.publish("user_onboarded", {"username": username, "id": new_user.id})
            return f"Onboarding complete. Welcome to the SATURDAY network, {username}."
        except Exception as e:
            logger.error(f"Error finalizing onboarding for {username}: {str(e)}")
            return f"Failed to finalize onboarding: {str(e)}"

    async def trigger_biometric_setup(self, username: str, biometric_type: str):
        
        if biometric_type == "face":
            self.event_bus.publish("face_enrollment_requested", {"username": username})
        elif biometric_type == "voice":
            self.event_bus.publish("voice_enrollment_requested", {"username": username})
        else:
            return f"Unknown biometric type: {biometric_type}"
        
        return f"Starting {biometric_type} ID enrollment..."
