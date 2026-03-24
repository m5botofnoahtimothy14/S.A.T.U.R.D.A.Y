param(
    [string]$OutputDirectory = "certs",
    [string]$CommonName = "aegis.local",
    [int]$DaysValid = 825
)

$ErrorActionPreference = "Stop"

$openssl = Get-Command openssl -ErrorAction SilentlyContinue
if (-not $openssl) {
    throw "OpenSSL is required. Install OpenSSL and ensure 'openssl' is on PATH."
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$certPath = Join-Path $OutputDirectory "gateway-cert.pem"
$keyPath = Join-Path $OutputDirectory "gateway-key.pem"

& $openssl.Source req `
    -x509 `
    -nodes `
    -newkey rsa:4096 `
    -keyout $keyPath `
    -out $certPath `
    -days $DaysValid `
    -subj "/CN=$CommonName"

Write-Host "Generated certificate: $certPath"
Write-Host "Generated key: $keyPath"
