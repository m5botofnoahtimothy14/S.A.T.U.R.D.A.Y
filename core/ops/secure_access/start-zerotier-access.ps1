param(
    [Parameter(Mandatory = $true)]
    [string]$NetworkId,
    [int]$GatewayPort = 8443
)

$ErrorActionPreference = "Stop"

$zt = Get-Command zerotier-cli -ErrorAction SilentlyContinue
if (-not $zt) {
    throw "zerotier-cli is required. Install ZeroTier One and add zerotier-cli to PATH."
}

& $zt.Source join $NetworkId
Start-Sleep -Seconds 4

$adapter = Get-NetAdapter | Where-Object {
    $_.InterfaceDescription -like "*ZeroTier*" -or $_.Name -like "*ZeroTier*"
} | Select-Object -First 1

if (-not $adapter) {
    throw "ZeroTier interface not detected after join. Verify network authorization in your ZeroTier controller."
}

$ruleName = "AEGIS Gateway ZeroTier $GatewayPort"
Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $GatewayPort `
    -InterfaceAlias $adapter.Name `
    -Profile Any | Out-Null

Write-Host "ZeroTier network joined: $NetworkId"
Write-Host "Firewall allows AEGIS API on interface '$($adapter.Name)' port $GatewayPort"
