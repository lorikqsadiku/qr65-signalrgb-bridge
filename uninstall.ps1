<#
.SYNOPSIS
  Removes the Edifier QR65 <-> SignalRGB bridge: stops it, deletes the autostart task and the
  SignalRGB plugin. Afterwards you can delete this folder.
#>
param(
    [string]$TaskName = 'QR65 BLE Bridge',
    [switch]$SkipPlugin
)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
# Only processes started from this folder.
$pattern = [regex]::Escape($here)
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -match $pattern } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; "Stopped PID $($_.ProcessId)" }

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    "Removed autostart task '$TaskName'"
}

if (-not $SkipPlugin) {
    $plugins = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'WhirlwindFX\Plugins'
    foreach ($f in 'EdifierQR65.js', 'EdifierQR65.qml') {
        $p = Join-Path $plugins $f
        if (Test-Path $p) { Remove-Item $p -Force; "Removed $p" }
    }
}

""
"Uninstalled. Restart SignalRGB, then you can delete this folder."
