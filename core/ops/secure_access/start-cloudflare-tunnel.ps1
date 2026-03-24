param(
    [int]$LocalPort = 8443,
    [string]$TunnelToken = $env:CLOUDFLARE_TUNNEL_TOKEN
)

$ErrorActionPreference = "Stop"

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    throw "cloudflared is required. Install it from Cloudflare and add it to PATH."
}

if ($TunnelToken) {
    & $cloudflared.Source tunnel run --token $TunnelToken
    exit $LASTEXITCODE
}

& $cloudflared.Source tunnel --url "https://127.0.0.1:$LocalPort" --no-tls-verify
