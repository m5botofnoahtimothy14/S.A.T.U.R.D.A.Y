# AEGIS OS - Setup and Build Script
# This script initializes the permanent environment for AEGIS.

Write-Host "--- AEGIS OS: Initializing Permanent Environment ---" -ForegroundColor Cyan

# 1. Create Virtual Environment if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "[1/4] Creating Virtual Environment..." -ForegroundColor Yellow
    python -m venv .venv
}
else {
    Write-Host "[1/4] Virtual Environment already exists." -ForegroundColor Gray
}

# 2. Upgrade Pip and Install Dependencies
Write-Host "[2/4] Installing/Updating Project Dependencies..." -ForegroundColor Yellow
& .venv\Scripts\python -m pip install --upgrade pip
& .venv\Scripts\python -m pip install -r requirements.txt

# 3. Initialize Databases
Write-Host "[3/4] Initializing AEGIS Databases..." -ForegroundColor Yellow
$initScript = @"
import sys
import os
sys.path.append(os.getcwd())
try:
    from identity.database import init_db
    init_db()
    print('Identity database initialized successfully.')
except Exception as e:
    print(f'Database init error: {e}')
"@
$initScript | & .venv\Scripts\python

# 4. Finalize Build
if (Setup-Path "logs" -ErrorAction SilentlyContinue) { } else { New-Item -ItemType Directory -Path "logs" -Force }
Write-Host "[4/4] Environment Ready." -ForegroundColor Green

Write-Host "`n--- BUILD COMPLETE ---" -ForegroundColor Cyan
Write-Host "To start AEGIS, run: .venv\Scripts\python core\main.py"
Write-Host "To install as Windows Service, run: .venv\Scripts\python services\windows_service.py install"
