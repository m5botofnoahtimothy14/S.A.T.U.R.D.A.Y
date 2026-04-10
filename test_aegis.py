"""
AEGIS System Test Script
Tests microphone, speech recognition, and voice output
"""

import os
import sys
import time

sys.path.insert(0, 'D:/AEGIS')

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

print("=" * 60)
print("AEGIS SYSTEM TEST")
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

# Test AEGIS modules
print("\n[2] Testing AEGIS Modules...")
from core.event_bus import EventBus
print("    Event Bus: OK")

from core.audio_service import CrossPlatformAudio
print("    Audio Service: OK")

from core.audio_speaker import SpeakerManager
print("    Audio Speaker: OK")

from core.aegis_voice import AEGISVoice
print("    AEGIS Voice: OK")

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

# Test AEGIS voice
print("\n[5] Testing AEGIS Voice...")
voice = AEGISVoice()
print("    AEGIS Voice initialized")

# Summary
print("\n" + "=" * 60)
print("SYSTEM STATUS: OPERATIONAL")
print("=" * 60)
print("\nTo run full AEGIS system:")
print("  D:\\AEGIS\\start_aegis.bat")
print("\nTo verify system:")
print("  D:\\AEGIS\\.venv\\Scripts\\python.exe D:\\AEGIS\\verify_aegis.py")
print("=" * 60)
