

import os
import sys

                                      
DRIVE_ROOT = r"D:\AEGIS"
DRIVE_ROOT_ALT = r"D:/AEGIS"

os.environ['AEGIS_ROOT'] = DRIVE_ROOT
os.environ['TF_HUB_CACHE_DIR'] = os.path.join(DRIVE_ROOT, ".tensorflow", "hub")
os.environ['HF_HOME'] = os.path.join(DRIVE_ROOT, ".huggingface")
os.environ['TORCH_HOME'] = os.path.join(DRIVE_ROOT, ".torch")
os.environ['TRANSFORMERS_CACHE'] = os.path.join(DRIVE_ROOT, ".huggingface", "transformers")
os.environ['DEEPFACE_HOME'] = os.path.join(DRIVE_ROOT, ".deepface")
os.environ['KERAS_HOME'] = os.path.join(DRIVE_ROOT, ".keras")
os.environ['ONNX_HOME'] = os.path.join(DRIVE_ROOT, ".onnx")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

                    
for _dir in [
    os.path.join(DRIVE_ROOT, ".tensorflow", "hub"),
    os.path.join(DRIVE_ROOT, ".huggingface"),
    os.path.join(DRIVE_ROOT, ".torch"),
    os.path.join(DRIVE_ROOT, ".deepface"),
    os.path.join(DRIVE_ROOT, ".keras"),
    os.path.join(DRIVE_ROOT, ".onnx"),
    os.path.join(DRIVE_ROOT, "models"),
]:
    os.makedirs(_dir, exist_ok=True)

print("=" * 60)
print("AEGIS Deep Learning Backend Verification")
print("=" * 60)
print(f"\nCache Location: {DRIVE_ROOT}")
print(f"TensorFlow Hub: {os.environ['TF_HUB_CACHE_DIR']}")
print(f"HuggingFace: {os.environ['HF_HOME']}")
print(f"PyTorch: {os.environ['TORCH_HOME']}")
print(f"DeepFace: {os.environ['DEEPFACE_HOME']}")
print()

results = {}

            
print("[1/5] TensorFlow...")
try:
    import tensorflow as tf
    print(f"  OK: TensorFlow {tf.__version__}")
    results['tensorflow'] = True
    results['tf_version'] = tf.__version__
    
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        print(f"  GPU: {len(gpus)} device(s) available")
        for gpu in gpus:
            print(f"    - {gpu}")
        results['gpu'] = True
    else:
        print("  GPU: Not available (CPU mode)")
        results['gpu'] = False
except ImportError as e:
    print(f"  FAIL: {e}")
    results['tensorflow'] = False

         
print("\n[2/5] PyTorch...")
try:
    import torch
    print(f"  OK: PyTorch {torch.__version__}")
    results['pytorch'] = True
    results['torch_version'] = torch.__version__
    
    if torch.cuda.is_available():
        print(f"  CUDA: {torch.version.cuda}")
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        results['cuda'] = True
    else:
        print("  CUDA: Not available (CPU mode)")
        results['cuda'] = False
except ImportError as e:
    print(f"  FAIL: {e}")
    results['pytorch'] = False

              
print("\n[3/5] ONNX Runtime...")
try:
    import onnxruntime as ort
    print(f"  OK: ONNX Runtime {ort.__version__}")
    print(f"  Providers: {ort.get_available_providers()}")
    results['onnx'] = True
except ImportError as e:
    print(f"  FAIL: {e}")
    results['onnx'] = False

          
print("\n[4/5] DeepFace...")
try:
    from deepface import DeepFace
    print("  OK: DeepFace installed")
    results['deepface'] = True
    
                       
    import numpy as np
    import cv2
    
                          
    dummy_img = np.zeros((224, 224, 3), dtype=np.uint8)
    
                                                      
    print("  Testing basic analysis...")
    try:
        result = DeepFace.analyze(dummy_img, actions=['emotion'], enforce_detection=False, silent=True)
        print("  OK: DeepFace analysis works")
    except Exception as e:
        print(f"  WARN: Analysis test failed (models may need download): {e}")
        
except ImportError as e:
    print(f"  FAIL: {e}")
    results['deepface'] = False

                
print("\n[5/5] Faster Whisper...")
try:
    from faster_whisper import WhisperModel
    print("  OK: Faster Whisper installed")
    results['faster_whisper'] = True
except ImportError as e:
    print(f"  FAIL: {e}")
    results['faster_whisper'] = False

         
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

all_ok = all([
    results.get('tensorflow', False),
    results.get('pytorch', False),
    results.get('onnx', False),
    results.get('deepface', False),
    results.get('faster_whisper', False),
])

if all_ok:
    print("\n[OK] All Deep Learning backends properly installed!")
else:
    print("\n[FAIL] Some backends missing. Run setup_dl_drive_d.bat to install.")

print(f"\nTensorFlow: {'[OK]' if results.get('tensorflow') else '[FAIL]'} {results.get('tf_version', '')}")
print(f"PyTorch: {'[OK]' if results.get('pytorch') else '[FAIL]'} {results.get('torch_version', '')}")
print(f"ONNX: {'[OK]' if results.get('onnx') else '[FAIL]'}")
print(f"DeepFace: {'[OK]' if results.get('deepface') else '[FAIL]'}")
print(f"Faster Whisper: {'[OK]' if results.get('faster_whisper') else '[FAIL]'}")

if results.get('gpu') or results.get('cuda'):
    print(f"\nGPU Acceleration: ✓ Available")
else:
    print(f"\nGPU Acceleration: ✗ Not available (CPU mode)")

print("\n" + "=" * 60)
