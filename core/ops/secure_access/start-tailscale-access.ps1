param(
    [int]$LocalPort = 8443,
    [int]$ServePort = 443,
    [switch]$EnableFunnel
)

$ErrorActionPreference = "Stop"

$tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $tailscale) {
    throw "tailscale CLI is required. Install Tailscale and add it to PATH."
}

& $tailscale.Source up --accept-dns=false --accept-routes
& $tailscale.Source serve --https=$ServePort "https://127.0.0.1:$LocalPort"

if ($EnableFunnel) {
    & $tailscale.Source funnel --https=$ServePort on
}

Write-Host "Tailscale HTTPS service is active."
Write-Host "Local API target: https://127.0.0.1:$LocalPort"
