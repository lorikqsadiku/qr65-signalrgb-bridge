<#
.SYNOPSIS
  Installs the Edifier QR65 <-> SignalRGB bridge for the current Windows user (no admin rights needed).

  1. finds Python 3.10+          4. finds your QR65 over Bluetooth (speaker in Bluetooth mode)
  2. installs bleak + aiohttp    5. creates the "QR65 BLE Bridge" autostart task (at logon)
  3. copies the SignalRGB plugin 6. starts the bridge and opens the color calibration page

  The options below are for testing/advanced use only.
#>
param(
    [string]$TaskName = 'QR65 BLE Bridge',
    [switch]$SkipPlugin,
    [switch]$SkipFind,
    [switch]$NoStart
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "   $text" -ForegroundColor Green }
function Info($text) { Write-Host "   $text" }
function Fail($text) { Write-Host ""; Write-Host $text -ForegroundColor Red; exit 1 }

# 1 -------------------------------------------------------------------------
Step 'Checking Python (3.10 or newer)'
$python = $null
foreach ($candidate in @(@{ Exe = 'py'; Args = @('-3') }, @{ Exe = 'python'; Args = @() })) {
    if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
    try {
        $out = & $candidate.Exe @($candidate.Args) -c "import sys; print(sys.executable if sys.version_info >= (3, 10) else '')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            $exe = ($out | Select-Object -Last 1).Trim()
            if ($exe -and (Test-Path $exe)) { $python = $exe; break }
        }
    } catch { }
}
if (-not $python) {
    Fail ("Python 3.10 or newer was not found.`n" +
          "Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'),`n" +
          "then run install.cmd again.")
}
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { Fail "pythonw.exe not found next to $python" }
Ok "Using $python"

# 2 -------------------------------------------------------------------------
Step 'Installing Python packages (bleak, aiohttp)'
& $python -m pip install --disable-pip-version-check --quiet -r (Join-Path $here 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Fail 'pip install failed (see messages above).' }
Ok 'Packages installed'

# 3 -------------------------------------------------------------------------
if (-not $SkipPlugin) {
    Step 'Installing the SignalRGB plugin'
    $plugins = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'WhirlwindFX\Plugins'
    New-Item -ItemType Directory -Force -Path $plugins | Out-Null
    Copy-Item (Join-Path $here 'signalrgb-plugin\*') $plugins -Force
    Ok "Copied to $plugins"
}

# 4 -------------------------------------------------------------------------
if (-not $SkipFind) {
    Step 'Looking for your Edifier QR65'
    $configFile = Join-Path $here 'qr65_config.json'
    $configured = $false
    if (Test-Path $configFile) {
        try { $configured = [bool]((Get-Content $configFile -Raw | ConvertFrom-Json).device_address) } catch { }
    }
    if ($configured) {
        Ok 'A speaker is already configured (qr65_config.json) - skipping the search.'
    } else {
        Info 'Switch the speaker on and press its input button until it is in BLUETOOTH mode.'
        Read-Host '   Then press Enter to search' | Out-Null
        Push-Location $here
        try { & $python (Join-Path $here 'qr65_bridge.py') --find } finally { Pop-Location }
        if ($LASTEXITCODE -ne 0) {
            Info 'Not found right now - no problem: the bridge keeps searching in the background and'
            Info 'remembers the speaker as soon as it is in Bluetooth mode (you will get a notification).'
        }
    }
}

# 5 -------------------------------------------------------------------------
Step "Creating the autostart task '$TaskName'"
$user = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument ('"{0}"' -f (Join-Path $here 'qr65_bridge_service.pyw')) -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description 'Edifier QR65 <-> SignalRGB lighting bridge' -Force | Out-Null
Ok 'Starts automatically when you log on to Windows'

# 6 -------------------------------------------------------------------------
if (-not $NoStart) {
    Step 'Starting the bridge'
    & (Join-Path $here 'qr65_restart_bridge.ps1') -TaskName $TaskName
    Start-Process 'http://127.0.0.1:5297/calibrate'
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
Write-Host "Next: (re)start SignalRGB - 'Edifier QR65' appears under Devices; place it in your layout."
Write-Host "Color calibration: http://127.0.0.1:5297/calibrate   (see README.txt / ANLEITUNG.txt)"
