#!/usr/bin/env python3

import os
import sys

def download_models():
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("ERROR: faster-whisper not installed. Run: pip install faster-whisper")
        sys.exit(1)
    
    model_dir = os.path.join(os.path.dirname(__file__), "..", "models", "whisper")
    os.makedirs(model_dir, exist_ok=True)
    
    models = {
        "tiny": "Fastest, ~1GB RAM",
        "base": "Balanced, ~1GB RAM",  
        "small": "Better accuracy, ~2GB RAM"
    }
    
    print("Available Whisper models for OFFLINE voice recognition:")
    for m, desc in models.items():
        print(f"  {m}: {desc}")
    print()
    
    default = os.getenv("WHISPER_MODEL_SIZE", "tiny")
    model_to_download = sys.argv[1] if len(sys.argv) > 1 else default
    
    if model_to_download not in models:
        print(f"Unknown model: {model_to_download}. Using 'tiny'.")
        model_to_download = "tiny"
    
    print(f"Downloading Whisper '{model_to_download}' model to {model_dir}...")
    print("This runs ONCE and works completely OFFLINE after.\n")
    
    try:
        model = WhisperModel(
            model_to_download,
            device="cpu",
            compute_type="int8",
            download_root=model_dir
        )
        print(f"\nSUCCESS: Whisper '{model_to_download}' downloaded to {model_dir}")
        print("\nSet in .env:")
        print(f"  WHISPER_MODEL_PATH={model_dir.replace(chr(92), '/')}")
        print(f"  WHISPER_MODEL_SIZE={model_to_download}")
        print("\nVoice recognition now works 100% OFFLINE with deep learning!")
    except Exception as e:
        print(f"ERROR downloading model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_models()
