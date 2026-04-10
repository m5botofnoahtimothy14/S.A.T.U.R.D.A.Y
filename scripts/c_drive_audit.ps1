$ErrorActionPreference = "SilentlyContinue"

function Get-DirSizeGB {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $sum = (Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum

    if ($null -eq $sum) {
        $sum = 0
    }

    return [math]::Round(($sum / 1GB), 2)
}

$drive = Get-PSDrive -Name C
if ($null -ne $drive) {
    [pscustomobject]@{
        UsedGB  = [math]::Round(($drive.Used / 1GB), 2)
        FreeGB  = [math]::Round(($drive.Free / 1GB), 2)
        TotalGB = [math]::Round((($drive.Used + $drive.Free) / 1GB), 2)
        UsedPct = [math]::Round((($drive.Used / ($drive.Used + $drive.Free)) * 100), 2)
    } | Format-List
}
else {
    "Could not read C: drive usage via Get-PSDrive."
}

""
"Top target folders (GB):"
$targets = @(
    "C:\Users",
    "C:\Windows",
    "C:\Program Files",
    "C:\Program Files (x86)",
    "C:\ProgramData",
    'C:\$Recycle.Bin',
    "C:\Windows\WinSxS",
    "C:\Windows\Installer",
    "C:\Windows\Temp"
)

$rows = foreach ($t in $targets) {
    $size = Get-DirSizeGB -Path $t
    if ($null -ne $size) {
        [pscustomobject]@{
            Path   = $t
            SizeGB = $size
        }
    }
}

$rows |
    Sort-Object -Property SizeGB -Descending |
    Format-Table -AutoSize
