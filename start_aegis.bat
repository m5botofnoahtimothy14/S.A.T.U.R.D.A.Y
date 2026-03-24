@echo off
setlocal
REM Ensure we run from the project root (this script's directory)
cd /d "%~dp0"
REM AEGIS AI OS - Startup Script
REM This starts AEGIS with Deep Learning capabilities

echo.
echo ============================================
echo    AEGIS AI OS - Deep Learning Powered
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment at "%cd%\.venv"
        pause
        exit /b 1
    )
)

REM Activate virtual environment
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

REM Install dependencies if needed
pip show numpy >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install numpy
)

REM Start AEGIS
echo Starting AEGIS AI OS...
echo.
echo IMPORTANT: To access remotely, use ngrok:
echo   1. Download ngrok from https://ngrok.com
echo   2. Run: ngrok http 8000
echo   3. Update .env with your ngrok URL
echo.

python -m core.main

pause
