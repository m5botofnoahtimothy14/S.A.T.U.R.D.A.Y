param(
    [int]$GatewayPort = 8443,
    [string]$AllowedSubnet = "192.168.0.0/24"
)

$ErrorActionPreference = "Stop"

$allowRule = "AEGIS Gateway Allow LAN $GatewayPort"
$blockRule = "AEGIS Gateway Block Internet $GatewayPort"

Get-NetFirewallRule -DisplayName $allowRule -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
Get-NetFirewallRule -DisplayName $blockRule -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue

New-NetFirewallRule `
    -DisplayName $allowRule `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $GatewayPort `
    -RemoteAddress $AllowedSubnet `
    -Profile Private | Out-Null

New-NetFirewallRule `
    -DisplayName $blockRule `
    -Direction Inbound `
    -Action Block `
    -Protocol TCP `
    -LocalPort $GatewayPort `
    -RemoteAddress Internet `
    -Profile Any | Out-Null

Write-Host "Firewall configured for AEGIS API port $GatewayPort"
Write-Host "Allowed subnet: $AllowedSubnet"
