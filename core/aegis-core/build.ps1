
param(
    [string]$BuildType = "Release"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path $MyInvocation.MyCommand.Path -Parent
$CoreDir = Join-Path $Root "aegis-core"
$BuildDir = Join-Path $CoreDir "build"
$BinDir = Join-Path $CoreDir "bin"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BUILDING AEGIS VISUAL CORE (C++)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath = $null

if (Test-Path $vsWhere) {
    $vsPath = & $vsWhere -latest -property installationPath -format value
    Write-Host "[OK] Visual Studio found: $vsPath" -ForegroundColor Green
} else {
    Write-Host "[WARN] Visual Studio not found via vswhere" -ForegroundColor Yellow
    Write-Host "       Please install Visual Studio 2019+" -ForegroundColor Yellow
}

$cmake = Get-Command cmake -ErrorAction SilentlyContinue
if (-not $cmake) {
    Write-Host "[ERROR] CMake not found!" -ForegroundColor Red
    Write-Host "       Install CMake: https://cmake.org/download/" -ForegroundColor Gray
    exit 1
}
Write-Host "[OK] CMake found: $($cmake.Source)" -ForegroundColor Green

if (-not (Test-Path $BuildDir)) {
    New-Item -ItemType Directory -Path $BuildDir | Out-Null
}

Write-Host ""
Write-Host "[1/2] Configuring CMake..." -ForegroundColor Yellow
Push-Location $BuildDir
try {
    cmake .. -G "Visual Studio 17 2022" -A x64 -DCMAKE_BUILD_TYPE=$BuildType
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Trying Visual Studio 2019..." -ForegroundColor Gray
        cmake .. -G "Visual Studio 16 2019" -A x64 -DCMAKE_BUILD_TYPE=$BuildType
    }
} finally {
    Pop-Location
}

Write-Host "[2/2] Building..." -ForegroundColor Yellow
Push-Location $BuildDir
try {
    cmake --build . --config $BuildType --parallel
} finally {
    Pop-Location
}

$ExePath = Join-Path $BinDir "aegis-core.exe"
if (Test-Path $ExePath) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  BUILD SUCCESSFUL!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Executable: $ExePath" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To run the startup animation:" -ForegroundColor Yellow
    Write-Host "  .\start_aegis.ps1" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "[ERROR] Build failed - executable not found" -ForegroundColor Red
    exit 1
}
