

Write-Host "--- SATURDAY OS: Initializing Permanent Environment ---" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    Write-Host "[1/4] Creating Virtual Environment..." -ForegroundColor Yellow
    python -m venv .venv
}
else {
    Write-Host "[1/4] Virtual Environment already exists." -ForegroundColor Gray
}
Write-Host "[2/4] Installing/Updating Project Dependencies..." -ForegroundColor Yellow
& .venv\Scripts\python -m pip install --upgrade pip
& .venv\Scripts\python -m pip install -r requirements.txt
Write-Host "[3/4] Initializing SATURDAY Databases..." -ForegroundColor Yellow
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
if (Setup-Path "logs" -ErrorAction SilentlyContinue) { } else { New-Item -ItemType Directory -Path "logs" -Force }
Write-Host "[4/4] Environment Ready." -ForegroundColor Green
Write-Host "`n--- BUILD COMPLETE ---" -ForegroundColor Cyan
Write-Host "To start SATURDAY, run: .venv\Scripts\python core\main.py"
Write-Host "To install as Windows Service, run: .venv\Scripts\python services\windows_service.py install"
