param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$EnvFile = ".\gateway.env",
    [string]$CertFile = ".\certs\gateway-cert.pem",
    [string]$KeyFile = ".\certs\gateway-key.pem",
    [string]$Host = "127.0.0.1",
    [int]$Port = 8443
)

$ErrorActionPreference = "Stop"

function Import-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
        $parts = $_.Split('=', 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ($name) { Set-Item -Path "Env:$name" -Value $value }
    }
}

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found at $PythonExe"
}
if (-not (Test-Path $CertFile)) {
    throw "TLS cert file not found at $CertFile"
}
if (-not (Test-Path $KeyFile)) {
    throw "TLS key file not found at $KeyFile"
}

Import-EnvFile -Path $EnvFile

$env:SATURDAY_API_HOST = $Host
$env:SATURDAY_API_PORT = "$Port"
$env:SATURDAY_SSL_CERT_FILE = (Resolve-Path $CertFile).Path
$env:SATURDAY_SSL_KEY_FILE = (Resolve-Path $KeyFile).Path

& $PythonExe .\api_gateway.py
