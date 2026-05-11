#!/usr/bin/env python3
import sys
import os
import argparse
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
def start_voice_mode():
    from core.event_bus import EventBus
    from core.voice_dl import SATURDAYVoiceDL
    from communication.speech import SpeechManager
    print("="*60)
    print("SATURDAY VOICE MODE")
    print("="*60)
    print()
    event_bus = EventBus()
    speech = SpeechManager()
    print(f"TTS Backend: {speech.backend}")
    saturday = SATURDAYVoiceDL(event_bus, llm_engine=None, speech_manager=speech)
    print(f"HomeBot: {'Connected' if saturday.homebot.connected else 'Offline'}")
    print(f"Whisper DL: {'Ready' if saturday.audio.whisper_model else 'Unavailable'}")
    print()
    print("Starting SATURDAY...")
    print()
    saturday.start()
    print("SATURDAY is listening. Speak naturally to command.")
    print("Press Ctrl+C to stop.")
    print()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down SATURDAY...")
        saturday.stop()
        print("SATURDAY stopped.")
def start_web_mode():
    import uvicorn
    from core.main import app
    print("="*60)
    print("SATURDAY WEB SERVER MODE")
    print("="*60)
    print()
    print("Starting web server at http://localhost:8000")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
def test_mode():
    print("="*60)
    print("SATURDAY TEST MODE")
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
    print("SATURDAY TEST COMPLETE")
    print("="*60)
def main():
    parser = argparse.ArgumentParser(description="SATURDAY AI System")
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
        start_voice_mode()
if __name__ == "__main__":
    main()
