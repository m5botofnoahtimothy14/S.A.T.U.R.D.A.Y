@echo off

echo ================================================
echo SATURDAY Deep Learning Setup - Drive D Edition
echo ================================================
echo.

setlocal enabledelayedexpansion

set "DRIVE=D:"
set "SATURDAY_ROOT=%DRIVE%\SATURDAY"
set "PYTHON_BIN=python"

echo [1/6] Creating Drive D directories...
mkdir "%DRIVE%\SATURDAY\.tensorflow" 2>nul
mkdir "%DRIVE%\SATURDAY\.huggingface" 2>nul
mkdir "%DRIVE%\SATURDAY\.torch" 2>nul
mkdir "%DRIVE%\SATURDAY\.onnx" 2>nul
mkdir "%DRIVE%\SATURDAY\.deepface" 2>nul
mkdir "%DRIVE%\SATURDAY\.keras" 2>nul
mkdir "%DRIVE%\SATURDAY\models" 2>nul
echo       Done: All cache directories created on Drive D
echo.

echo [2/6] Setting environment variables...
setx SATURDAY_ROOT "%SATURDAY_ROOT%"
setx TF_CPP_MIN_LOG_LEVEL "3"
setx TF_HUB_CACHE_DIR "%DRIVE%\SATURDAY\.tensorflow\hub"
setx HF_HOME "%DRIVE%\SATURDAY\.huggingface"
setx TORCH_HOME "%DRIVE%\SATURDAY\.torch"
setx TRANSFORMERS_CACHE "%DRIVE%\SATURDAY\.huggingface\transformers"
setx DEEPFACE_HOME "%DRIVE%\SATURDAY\.deepface"
setx KERAS_HOME "%DRIVE%\SATURDAY\.keras"
setx ONNX_HOME "%DRIVE%\SATURDAY\.onnx"
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
echo   - TensorFlow: %DRIVE%\SATURDAY\.tensorflow
echo   - HuggingFace: %DRIVE%\SATURDAY\.huggingface
echo   - PyTorch: %DRIVE%\SATURDAY\.torch
echo   - DeepFace: %DRIVE%\SATURDAY\.deepface
echo   - Models: %DRIVE%\SATURDAY\models
echo.
echo Running verification...
echo.

%PYTHON_BIN% -c "
import os
os.environ['SATURDAY_ROOT'] = r'%SATURDAY_ROOT%'
os.environ['TF_HUB_CACHE_DIR'] = r'%DRIVE%\SATURDAY\.tensorflow\hub'
os.environ['HF_HOME'] = r'%DRIVE%\SATURDAY\.huggingface'
os.environ['TORCH_HOME'] = r'%DRIVE%\SATURDAY\.torch'
os.environ['DEEPFACE_HOME'] = r'%DRIVE%\SATURDAY\.deepface'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

print('='*50)
print('SATURDAY DL Backend Verification')
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
