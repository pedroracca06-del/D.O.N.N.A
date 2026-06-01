# schedule_session.ps1
# Registers a Windows Task Scheduler entry that auto-fires start_trading_session.ps1
# at 9:15 AM ET, Monday–Friday.
#
# Run once (as admin or normal user — Task Scheduler allows user-level tasks):
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_session.ps1

$DONNA_DIR     = Split-Path $PSScriptRoot -Parent
$LAUNCHER      = Join-Path $DONNA_DIR "scripts\start_trading_session.ps1"
$TASK_NAME     = "DONNA_TradingSession"

$action  = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-WindowStyle Normal -ExecutionPolicy Bypass -File `"$LAUNCHER`""

# 9:15 AM daily; days-of-week filter applied in trigger
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "09:15AM"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -StartWhenAvailable

# Register (or overwrite if it already exists)
Register-ScheduledTask `
    -TaskName   $TASK_NAME `
    -Action     $action `
    -Trigger    $trigger `
    -Settings   $settings `
    -RunLevel   Limited `
    -Force | Out-Null

Write-Host ""
Write-Host "Task registered: $TASK_NAME" -ForegroundColor Green
Write-Host "  Fires: Mon-Fri at 9:15 AM"
Write-Host "  Launches: start_trading_session.ps1"
Write-Host ""
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TASK_NAME' -Confirm:`$false"
