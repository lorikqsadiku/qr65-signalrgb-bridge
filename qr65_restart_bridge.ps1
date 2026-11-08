<#
.SYNOPSIS
  (Re)start the QR65 bridge: stop every running copy, then start the "QR65 BLE Bridge" scheduled task.

.PARAMETER ConfigureTask
  Also fix the scheduled task (needs an admin PowerShell, only once):
    - remove the 72-hour execution time limit (it killed the restart wrapper every 3 days)
    - run with normal user rights instead of "highest privileges" (BLE needs no admin; this also
      means later restarts don't need admin)

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File qr65_restart_bridge.ps1 -ConfigureTask   # first time, as admin
  powershell -ExecutionPolicy Bypass -File qr65_restart_bridge.ps1                  # any later restart
#>
param([switch]$ConfigureTask, [string]$TaskName = 'QR65 BLE Bridge')

$ErrorActionPreference = 'Stop'
$taskName = $TaskName

if ($ConfigureTask) {
    # Task Scheduler COM API: edits the definition in place, so the stored account (a SID) is kept as-is.
    try {
        $svc = New-Object -ComObject Schedule.Service
        $svc.Connect()
        $folder = $svc.GetFolder('\')
        $def = $folder.GetTask($taskName).Definition
        $def.Settings.ExecutionTimeLimit = 'PT0S'   # PT0S = no limit (default was 72 hours)
        $def.Principal.RunLevel = 0                 # TASK_RUNLEVEL_LUA = normal user rights
        $null = $folder.RegisterTaskDefinition($taskName, $def, 4, $null, $null, 3)  # TASK_UPDATE, interactive token
        $check = $folder.GetTask($taskName).Definition
        "Task updated: time limit='$($check.Settings.ExecutionTimeLimit)' (PT0S = none), runLevel=$($check.Principal.RunLevel) (0 = normal rights)."
    } catch {
        "Could not update the task ($($_.Exception.Message)); continuing with the restart."
    }
}

# Stop the task, the wrapper and every bridge process (old or new).
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$ids = @()
$ids += Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match 'qr65_bridge' } | ForEach-Object { $_.ProcessId }
$ids += (Get-NetTCPConnection -LocalPort 5297 -State Listen -ErrorAction SilentlyContinue).OwningProcess
foreach ($id in ($ids | Where-Object { $_ } | Sort-Object -Unique)) {
    try { Stop-Process -Id $id -Force -ErrorAction Stop; "Stopped PID $id" }
    catch { "Could not stop PID $id ($($_.Exception.Message)) - run this from an admin PowerShell" }
}
Start-Sleep -Seconds 2

Start-ScheduledTask -TaskName $taskName
"Started '$taskName'. Waiting for the bridge..."
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try { $s = Invoke-RestMethod http://127.0.0.1:5297/status -TimeoutSec 2; break } catch { $s = $null }
}
if ($s) { "Bridge is up: state=$($s.state) connected=$($s.connected)" }
else { "Bridge did not answer - check qr65_bridge.log and qr65_bridge_stderr.log" }
