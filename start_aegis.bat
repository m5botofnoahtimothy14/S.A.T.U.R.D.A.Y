@echo off
setlocal
cd /d "%~dp0"
echo.
echo ============================================
echo    AEGIS AI OS - Deep Learning Powered
echo ============================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+
    pause
    exit /b 1
)
set PYTHONPATH=%CD%\pip_packages;F:\aegis_packages;%PYTHONPATH%
set TF_HUB_CACHE_DIR=%CD%\.tensorflow\hub
set HF_HOME=%CD%\.huggingface
set TORCH_HOME=%CD%\.torch
set DEEPFACE_HOME=%CD%\.deepface
set KERAS_HOME=%CD%\.keras
set TMP=F:\pip_temp
set TEMP=F:\pip_temp
mkdir ".\.tensorflow" 2>nul
mkdir ".\.huggingface" 2>nul
mkdir ".\.torch" 2>nul
mkdir ".\.deepface" 2>nul
mkdir ".\.keras" 2>nul
mkdir "F:\pip_temp" 2>nul
echo.
echo Disk Space Status:
python -c "import psutil; c=psutil.disk_usage('C:'); print(f'  C: {c.percent:.1f}% used ({c.free/1024**3:.1f}GB free)')"
python -c "import psutil; d=psutil.disk_usage('D:'); print(f'  D: {d.percent:.1f}% used ({d.free/1024**3:.1f}GB free)')"
python -c "import psutil; f=psutil.disk_usage('F:'); print(f'  F: {f.percent:.1f}% used ({f.free/1024**3:.1f}GB free)')"
echo.
echo Package Status:
python -c "
import sys
sys.path.insert(0, r'%CD%\pip_packages')
sys.path.insert(0, r'F:\aegis_packages')
packages = {
    'numpy': 'numpy',
    'scipy': 'scipy',
    'tensorflow': 'tensorflow',
    'torch': 'torch',
    'transformers': 'transformers',
    'onnxruntime': 'onnxruntime',
}
for name, module in packages.items():
    try:
        m = __import__(module)
        ver = getattr(m, '__version__', 'installed')
        print(f'  [OK] {name}: {ver}')
    except Exception as e:
        print(f'  [MISSING] {name}')
"
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment at "%cd%\.venv"
        pause
        exit /b 1
    )
)
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment activation script not found: "%cd%\.venv\Scripts\activate.bat"
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)
pip show numpy >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install numpy
)
echo.
echo Starting AEGIS AI OS...
echo.
echo IMPORTANT: To access remotely, use ngrok:
echo   1. Download ngrok from https://ngrok.com
echo   2. Run: ngrok http 8000
echo   3. Update .env with your ngrok URL
echo.
python -m core.main
pause
