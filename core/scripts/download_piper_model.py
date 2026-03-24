#!/usr/bin/env python3
"""
Download Piper TTS models for OFFLINE deep learning text-to-speech.
"""
import os
import urllib.request
import zipfile

MODELS = {
    "en_US-lessac-medium": {
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "config_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
        "description": "Deep learning TTS - American English, medium quality"
    },
    "en_US-lessac-large": {
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/large/en_US-lessac-large.onnx",
        "config_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/large/en_US-lessac-large.onnx.json",
        "description": "Deep learning TTS - American English, high quality"
    }
}

def download_file(url, dest):
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, dest)
    print(f"Saved to {dest}")

def main():
    model_dir = os.path.join(os.path.dirname(__file__), "..", "models", "piper")
    os.makedirs(model_dir, exist_ok=True)
    
    print("Available Piper TTS models for OFFLINE deep learning speech:")
    for name, info in MODELS.items():
        print(f"  {name}: {info['description']}")
    print()
    
    model_name = os.getenv("PIPER_MODEL", "en_US-lessac-medium")
    if model_name not in MODELS:
        model_name = "en_US-lessac-medium"
    
    info = MODELS[model_name]
    model_path = os.path.join(model_dir, f"{model_name}.onnx")
    config_path = os.path.join(model_dir, f"{model_name}.onnx.json")
    
    if not os.path.exists(model_path):
        download_file(info["url"], model_path)
        download_file(info["config_url"], config_path)
        print(f"\nModel downloaded: {model_path}")
    else:
        print(f"Model already exists: {model_path}")
    
    print(f"\nSet in .env:")
    print(f"  PIPER_MODEL_PATH={model_path.replace(chr(92), '/')}")
    print("\nTTS now works 100% OFFLINE with deep learning!")

if __name__ == "__main__":
    main()
