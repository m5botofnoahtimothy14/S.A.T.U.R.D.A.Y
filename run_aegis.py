#!/usr/bin/env python3
"""
AEGIS - Advanced Evolving General Intelligence System
======================================================
Start the full AEGIS system with voice control.

Usage:
    python run_aegis.py              # Start AEGIS
    python run_aegis.py --voice      # Start with voice
    python run_aegis.py --web        # Start web server only
    python run_aegis.py --test       # Test mode (no voice)
"""
import sys
import os
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


def start_voice_mode():
    """Start AEGIS with full voice control"""
    from core.event_bus import EventBus
    from core.voice_dl import AEGISVoiceDL
    from communication.speech import SpeechManager
    
    print("="*60)
    print("AEGIS VOICE MODE")
    print("="*60)
    print()
    
    event_bus = EventBus()
    speech = SpeechManager()
    print(f"TTS Backend: {speech.backend}")
    
    aegis = AEGISVoiceDL(event_bus, llm_engine=None, speech_manager=speech)
    print(f"HomeBot: {'Connected' if aegis.homebot.connected else 'Offline'}")
    print(f"Whisper DL: {'Ready' if aegis.audio.whisper_model else 'Unavailable'}")
    
    print()
    print("Starting AEGIS...")
    print()
    
    aegis.start()
    
    print("AEGIS is listening. Speak naturally to command.")
    print("Press Ctrl+C to stop.")
    print()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down AEGIS...")
        aegis.stop()
        print("AEGIS stopped.")


def start_web_mode():
    """Start AEGIS web server only"""
    import uvicorn
    from core.main import app
    
    print("="*60)
    print("AEGIS WEB SERVER MODE")
    print("="*60)
    print()
    print("Starting web server at http://localhost:8000")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


def test_mode():
    """Test mode - no voice"""
    print("="*60)
    print("AEGIS TEST MODE")
    print("="*60)
    print()
    
    from core.event_bus import EventBus
    from core.voice_dl import SystemControl, HomeBotController, FileManager
    
    event_bus = EventBus()
    
    print("[1] System Control")
    sys_info = SystemControl.get_system_info()
    print("    OK - Can execute commands")
    
    print()
    print("[2] HomeBot Controller")
    hb = HomeBotController(event_bus)
    print(f"    Status: {'Connected' if hb.connected else 'Offline'}")
    
    print()
    print("[3] File Manager")
    fm = FileManager()
    print("    OK")
    
    print()
    print("="*60)
    print("AEGIS TEST COMPLETE")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description="AEGIS AI System")
    parser.add_argument("--voice", action="store_true", help="Start with voice control")
    parser.add_argument("--web", action="store_true", help="Start web server only")
    parser.add_argument("--test", action="store_true", help="Test mode")
    args = parser.parse_args()
    
    if args.test:
        test_mode()
    elif args.voice:
        start_voice_mode()
    elif args.web:
        start_web_mode()
    else:
        # Default: start voice mode
        start_voice_mode()


if __name__ == "__main__":
    main()
