$ErrorActionPreference = "Stop"

$installerPath = "D:\git-installer.exe"
$downloadUrl = "https://github.com/git-for-windows/git/releases/latest/download/Git-64-bit.exe"

Write-Output "Downloading Git installer..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath
} catch {
    Write-Output "Invoke-WebRequest failed, trying BITS download..."
    Start-BitsTransfer -Source $downloadUrl -Destination $installerPath
}

Write-Output "Installing Git silently..."
Start-Process -FilePath $installerPath -ArgumentList "/VERYSILENT", "/NORESTART", "/SP-", "/SUPPRESSMSGBOXES" -Wait

Write-Output "Git install complete."
