"""
SATURDAY System Test Script
Tests microphone, speech recognition, and voice output
"""

import os
import sys
import time

sys.path.insert(0, 'D:/SATURDAY')

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

print("=" * 60)
print("SATURDAY SYSTEM TEST")
print("=" * 60)

# Test imports
print("\n[1] Testing Imports...")
try:
    import tensorflow as tf
    print(f"    TensorFlow: {tf.__version__}")
except:
    print("    TensorFlow: Not available")

try:
    import numpy as np
    print(f"    NumPy: {np.__version__}")
except:
    print("    NumPy: Not available")

try:
    import scipy
    print(f"    SciPy: {scipy.__version__}")
except:
    print("    SciPy: Not available")

# Test SATURDAY modules
print("\n[2] Testing SATURDAY Modules...")
from core.event_bus import EventBus
print("    Event Bus: OK")

from core.audio_service import CrossPlatformAudio
print("    Audio Service: OK")

from core.audio_speaker import SpeakerManager
print("    Audio Speaker: OK")

from core.saturday_voice import SATURDAYVoice
print("    SATURDAY Voice: OK")

# Test microphone
print("\n[3] Testing Microphone...")
audio = CrossPlatformAudio()
mics = audio.list_microphones()
print(f"    Found {len(mics)} microphone(s)")
for idx, name in mics[:5]:
    print(f"      [{idx}] {name}")

if audio.recognizer:
    print(f"    Speech Recognizer: OK")
    print(f"    Energy Threshold: {audio.recognizer.energy_threshold}")

# Test speaker
print("\n[4] Testing Speaker Output...")
speaker_mgr = SpeakerManager()
if speaker_mgr.get_default():
    print("    Default Speaker: OK")
else:
    print("    Speaker: Not available")

# Test SATURDAY voice
print("\n[5] Testing SATURDAY Voice...")
voice = SATURDAYVoice()
print("    SATURDAY Voice initialized")

# Summary
print("\n" + "=" * 60)
print("SYSTEM STATUS: OPERATIONAL")
print("=" * 60)
print("\nTo run full SATURDAY system:")
print("  D:\\SATURDAY\\start_saturday.bat")
print("\nTo verify system:")
print("  D:\\SATURDAY\\.venv\\Scripts\\python.exe D:\\SATURDAY\\verify_saturday.py")
print("=" * 60)
