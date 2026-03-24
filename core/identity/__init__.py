# identity/__init__.py
from .manager import IdentityManager
from .onboarding import OnboardingManager
from .face_id import FaceID
from .voice_id import VoiceID
from .trust_engine import TrustEngine
from .behavioral_biometrics import BehavioralBiometrics

__all__ = [
    "IdentityManager",
    "OnboardingManager",
    "FaceID",
    "VoiceID",
    "TrustEngine",
    "BehavioralBiometrics"
]
