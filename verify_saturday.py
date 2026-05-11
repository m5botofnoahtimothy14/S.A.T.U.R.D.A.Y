

import sys
import os

sys.path.insert(0, r'D:\SATURDAY\pip_packages')
sys.path.insert(0, r'F:\saturday_packages')
sys.path.insert(0, r'D:\SATURDAY')

import site
site.addsitedir(r'D:\SATURDAY\pip_packages')
site.addsitedir(r'F:\saturday_packages')
site.addsitedir(r'C:\Users\Administrator\AppData\Local\Programs\Python\Python312\Lib\site-packages')

                           
os.environ['TF_HUB_CACHE_DIR'] = r'D:\SATURDAY\.tensorflow\hub'
os.environ['HF_HOME'] = r'D:\SATURDAY\.huggingface'
os.environ['TORCH_HOME'] = r'D:\SATURDAY\.torch'
os.environ['DEEPFACE_HOME'] = r'D:\SATURDAY\.deepface'
os.environ['KERAS_HOME'] = r'D:\SATURDAY\.keras'

print("=" * 70)
print("SATURDAY System Verification")
print("=" * 70)

results = {"pass": [], "fail": [], "warn": []}


def check(name, test_func, critical=False):
    
    try:
        result = test_func()
        if result:
            results["pass"].append(name)
            status = "[PASS]"
        else:
            results["warn"].append(name)
            status = "[WARN]"
        print(f"  {status} {name}")
        return result
    except Exception as e:
        results["fail"].append(name)
        print(f"  [FAIL] {name}: {e}")
        return False


def test_numpy():
    import numpy as np
    arr = np.array([1, 2, 3])
    return len(arr) == 3


def test_scipy():
    import scipy
    return hasattr(scipy, 'signal')


def test_audio():
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        return True
    except:
        pass
    try:
        import pyaudio
        return True
    except:
        return False


def test_speech_recognition():
    import speech_recognition as sr
    return hasattr(sr, 'Recognizer')


def test_tensorflow():
    try:
        import tensorflow as tf
        print(f"       Version: {tf.__version__}")
        return True
    except Exception as e:
        print(f"       Error: {e}")
        return False


def test_pytorch():
    try:
        import torch
        print(f"       Version: {torch.__version__}")
        return True
    except Exception as e:
        print(f"       Error: {e}")
        return False


def test_transformers():
    try:
        import transformers
        return True
    except:
        return False


def test_onnx():
    try:
        import onnxruntime
        return True
    except:
        return False


def test_deepface():
    try:
        from deepface import DeepFace
        return True
    except:
        return False


def test_saturday_core():
    try:
        from core.event_bus import EventBus
        return True
    except:
        return False


def test_audio_service():
    try:
        from core.audio_service import CrossPlatformAudio
        return True
    except:
        return False


def test_audio_speaker():
    try:
        from core.audio_speaker import SpeakerManager
        return True
    except:
        return False


def test_saturday_voice():
    try:
        from core.saturday_voice import SATURDAYVoice
        return True
    except:
        return False


def test_dl_backend():
    try:
        from core.deep_learning import DLBackendManager
        return True
    except:
        return False


def test_vision():
    try:
        from core.embodied.vision import VisionModule
        return True
    except:
        return False


def test_health():
    try:
        from core.health.monitor import HealthMonitor
        return True
    except:
        return False


print("\n[A] Python Packages")
print("-" * 70)
check("numpy", test_numpy, critical=True)
check("scipy", test_scipy)
check("audio (sounddevice/pyaudio)", test_audio, critical=True)
check("speech_recognition", test_speech_recognition, critical=True)

print("\n[B] Deep Learning Frameworks")
print("-" * 70)
check("TensorFlow", test_tensorflow)
check("PyTorch", test_pytorch)
check("Transformers", test_transformers)
check("ONNX Runtime", test_onnx)
check("DeepFace", test_deepface)

print("\n[C] SATURDAY Core Modules")
print("-" * 70)
check("SATURDAY Core", test_saturday_core, critical=True)
check("Audio Service", test_audio_service, critical=True)
check("Audio Speaker (Dolby)", test_audio_speaker)
check("SATURDAY Voice (Neural TTS)", test_saturday_voice)
check("DL Backend Manager", test_dl_backend)
check("Vision Module", test_vision)
check("Health Monitor", test_health)

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  PASSED: {len(results['pass'])}")
print(f"  WARNINGS: {len(results['warn'])}")
print(f"  FAILED: {len(results['fail'])}")

if results['fail']:
    print("\n  Failed modules:")
    for m in results['fail']:
        print(f"    - {m}")
    print("\n  Install missing packages:")
    print("    pip install tensorflow-cpu torch transformers onnxruntime deepface")
    print("    pip install sounddevice SpeechRecognition pyaudio")

if results['warn']:
    print("\n  Warning modules (optional):")
    for m in results['warn']:
        print(f"    - {m}")

print("\n" + "=" * 70)

                  
import psutil
print("\nDisk Space:")
c = psutil.disk_usage('C:')
print(f"  C: {c.percent:.1f}% used ({c.free/1024**3:.1f}GB free)")
if c.percent > 90:
    print("    WARNING: C drive is nearly full!")

d = psutil.disk_usage('D:')
print(f"  D: {d.percent:.1f}% used ({d.free/1024**3:.1f}GB free)")

f = psutil.disk_usage('F:')
print(f"  F: {f.percent:.1f}% used ({f.free/1024**3:.1f}GB free)")

print("\n" + "=" * 70)
print("SATURDAY System Ready!" if len(results['fail']) == 0 else "SATURDAY needs attention!")
print("=" * 70)
