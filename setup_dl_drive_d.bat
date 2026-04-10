@echo off

echo ================================================
echo AEGIS Deep Learning Setup - Drive D Edition
echo ================================================
echo.

setlocal enabledelayedexpansion

set "DRIVE=D:"
set "AEGIS_ROOT=%DRIVE%\AEGIS"
set "PYTHON_BIN=python"

echo [1/6] Creating Drive D directories...
mkdir "%DRIVE%\AEGIS\.tensorflow" 2>nul
mkdir "%DRIVE%\AEGIS\.huggingface" 2>nul
mkdir "%DRIVE%\AEGIS\.torch" 2>nul
mkdir "%DRIVE%\AEGIS\.onnx" 2>nul
mkdir "%DRIVE%\AEGIS\.deepface" 2>nul
mkdir "%DRIVE%\AEGIS\.keras" 2>nul
mkdir "%DRIVE%\AEGIS\models" 2>nul
echo       Done: All cache directories created on Drive D
echo.

echo [2/6] Setting environment variables...
setx AEGIS_ROOT "%AEGIS_ROOT%"
setx TF_CPP_MIN_LOG_LEVEL "3"
setx TF_HUB_CACHE_DIR "%DRIVE%\AEGIS\.tensorflow\hub"
setx HF_HOME "%DRIVE%\AEGIS\.huggingface"
setx TORCH_HOME "%DRIVE%\AEGIS\.torch"
setx TRANSFORMERS_CACHE "%DRIVE%\AEGIS\.huggingface\transformers"
setx DEEPFACE_HOME "%DRIVE%\AEGIS\.deepface"
setx KERAS_HOME "%DRIVE%\AEGIS\.keras"
setx ONNX_HOME "%DRIVE%\AEGIS\.onnx"
echo       Done: Environment variables configured
echo.

echo [3/6] Upgrading pip...
%PYTHON_BIN% -m pip install --upgrade pip --quiet
echo.

echo [4/6] Installing TensorFlow with GPU support...
%PYTHON_BIN% -m pip install tensorflow[and-cuda]>=2.15.0 --quiet 2>nul || (
    echo       Falling back to standard TensorFlow...
    %PYTHON_BIN% -m pip install tensorflow>=2.15.0 --quiet
)
echo.

echo [5/6] Installing DeepFace and vision dependencies...
%PYTHON_BIN% -m pip install deepface --quiet
%PYTHON_BIN% -m pip install retina-face --quiet
%PYTHON_BIN% -m pip install opencv-python-headless --quiet
%PYTHON_BIN% -m pip install Pillow --quiet
echo.

echo [6/6] Installing PyTorch with CUDA support...
%PYTHON_BIN% -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --quiet 2>nul || (
    echo       Falling back to CPU-only PyTorch...
    %PYTHON_BIN% -m pip install torch torchvision --quiet
)
echo.

echo.
echo ================================================
echo Installation Complete!
echo ================================================
echo.
echo Cache locations configured on Drive D:
echo   - TensorFlow: %DRIVE%\AEGIS\.tensorflow
echo   - HuggingFace: %DRIVE%\AEGIS\.huggingface
echo   - PyTorch: %DRIVE%\AEGIS\.torch
echo   - DeepFace: %DRIVE%\AEGIS\.deepface
echo   - Models: %DRIVE%\AEGIS\models
echo.
echo Running verification...
echo.

%PYTHON_BIN% -c "
import os
os.environ['AEGIS_ROOT'] = r'%AEGIS_ROOT%'
os.environ['TF_HUB_CACHE_DIR'] = r'%DRIVE%\AEGIS\.tensorflow\hub'
os.environ['HF_HOME'] = r'%DRIVE%\AEGIS\.huggingface'
os.environ['TORCH_HOME'] = r'%DRIVE%\AEGIS\.torch'
os.environ['DEEPFACE_HOME'] = r'%DRIVE%\AEGIS\.deepface'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

print('='*50)
print('AEGIS DL Backend Verification')
print('='*50)

# TensorFlow
try:
    import tensorflow as tf
    print(f'[OK] TensorFlow {tf.__version__}')
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        print(f'     GPU: {len(gpus)} device(s) available')
    else:
        print('     Running on CPU')
except ImportError:
    print('[FAIL] TensorFlow not installed')

# PyTorch
try:
    import torch
    print(f'[OK] PyTorch {torch.__version__}')
    if torch.cuda.is_available():
        print(f'     CUDA: {torch.version.cuda}')
    else:
        print('     Running on CPU')
except ImportError:
    print('[FAIL] PyTorch not installed')

# DeepFace
try:
    from deepface import DeepFace
    print('[OK] DeepFace installed')
except ImportError:
    print('[FAIL] DeepFace not installed')

# ONNX
try:
    import onnxruntime as ort
    print(f'[OK] ONNX Runtime {ort.__version__}')
except ImportError:
    print('[WARN] ONNX Runtime not installed')

print('='*50)
print('All DL frameworks configured for Drive D!')
print('='*50)
"

echo.
echo Press any key to exit...
pause >nul
