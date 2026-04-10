@echo off
echo ================================================
echo AEGIS Installation Script - Drive D Edition
echo ================================================
echo.

set PYTHON_TARGET=D:\AEGIS\pip_packages
set DL_CACHE=D:\AEGIS\.cache
set TEMP_DIR=D:\AEGIS\temp

echo Creating directories...
mkdir "%PYTHON_TARGET%" 2>nul
mkdir "%DL_CACHE%" 2>nul
mkdir "%TEMP_DIR%" 2>nul
echo.

set PYTHONPATH=%PYTHON_TARGET%;%PYTHONPATH%
set TMP=%TEMP_DIR%
set TEMP=%TEMP_DIR%

echo [1/10] Installing numpy and scipy (foundation)...
python -m pip install numpy scipy --target="%PYTHON_TARGET%" --no-cache-dir --quiet
echo.

echo [2/10] Installing sounddevice and speech_recognition...
python -m pip install sounddevice SpeechRecognition pyaudio --target="%PYTHON_TARGET%" --no-cache-dir --quiet
echo.

echo [3/10] Installing TensorFlow (CPU version for stability)...
python -m pip install tensorflow-cpu --target="%PYTHON_TARGET%" --no-cache-dir --quiet
echo.

echo [4/10] Installing PyTorch (CPU version)...
python -m pip install torch torchvision --target="%PYTHON_TARGET%" --index-url https://download.pytorch.org/whl/cpu --no-cache-dir --quiet
echo.

echo [5/10] Installing ONNX Runtime...
python -m pip install onnxruntime --target="%PYTHON_TARGET%" --no-cache-dir --quiet
echo.

echo [6/10] Installing faster-whisper...
python -m pip install faster-whisper --target="%PYTHON_TARGET%" --no-cache-dir --quiet
echo.

echo [7/10] Installing DeepFace dependencies...
python -m pip install deepface retina-face --target="%PYTHON_TARGET%" --no-cache-dir --quiet
echo.

echo [8/10] Installing opencv and Pillow...
python -m pip install opencv-python-headless Pillow --target="%PYTHON_TARGET%" --no-cache-dir --quiet
echo.

echo [9/10] Installing transformers and huggingface hub...
python -m pip install transformers huggingface_hub --target="%PYTHON_TARGET%" --no-cache-dir --quiet
echo.

echo [10/10] Installing other dependencies...
python -m pip install pyttsx3 pywin32 psutil paho-mqtt --target="%PYTHON_TARGET%" --no-cache-dir --quiet
echo.

echo.
echo ================================================
echo Installation Complete!
echo ================================================
echo.
echo Packages installed to: %PYTHON_TARGET%
echo.

echo Press any key to verify installation...
pause >nul
