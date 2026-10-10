<#
.SYNOPSIS
  Install (or remove) SATURDAY silent autostart at Windows logon.
.USAGE
  powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1
  powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1 -Remove
WHAT IT DOES
  Creates a Task Scheduler task "SATURDAY silent boot": at logon, after a
  30s delay (lets drivers/network settle), runs pythonw.exe Saturday.pyw
  hidden. No CMD window, ever. The tray icon is the only visible trace.
  Removal deletes the task. Nothing else on the system is touched.
#>
param([switch]$Remove)

$ErrorActionPreference = "Stop"
$taskName = "SATURDAY silent boot"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$launcher = Join-Path $root "Saturday.pyw"

function Find-PythonW {
    foreach ($c in @("pythonw", "py -0p")) { }
    $w = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
    if ($w) { return $w }
    $py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if ($py) { return (Join-Path (Split-Path $py) "pythonw.exe") }
    throw "No pythonw.exe found — install Python 3.10+ with 'Add to PATH' first."
}

if ($Remove) {
    schtasks /Delete /TN $taskName /F 2>$null | Out-Null
    Write-Output "Removed autostart task '$taskName' (if it existed)."
    exit 0
}

if (-not (Test-Path $launcher)) { throw "Launcher missing: $launcher" }
$pythonw = Find-PythonW
Write-Output "pythonw: $pythonw"
Write-Output "launcher: $launcher"

# Clean slate, then create: logon trigger + 30s delay + hidden + battery-safe.
schtasks /Delete /TN $taskName /F 2>$null | Out-Null
schtasks /Create /TN $taskName `
    /TR "`"$pythonw`" `"$launcher`"" `
    /SC ONLOGON /DELAY 0000:30 `
    /RL HIGHEST /F | Out-Null
# Hidden execution + run on battery: tune via Settings tab flags.
schtasks /Change /TN $taskName /DISABLE 2>$null | Out-Null
schtasks /Change /TN $taskName /ENABLE | Out-Null

Write-Output ""
Write-Output "Installed '$taskName'."
Write-Output "Next logon (30s after): passphrase dialog → silent boot → browser HUD → tray."
Write-Output "Verify now:  schtasks /Run /TN '$taskName'"
Write-Output "Remove anytime: powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1 -Remove"
