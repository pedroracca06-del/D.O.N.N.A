# start_trading_session.ps1
# Starts TradingView (CDP mode) + NOVA feed server.
# Triggered automatically by Task Scheduler at 09:15 ET Mon-Fri.
#
# CONTROLLED RETIREMENT (2026-07-16): the legacy trading/execution subsystem
# is retired. This script no longer enables auto-execution and no longer
# launches monitor.py (its only purpose was the retired reasoning->execution
# pipeline). See nova_knowledge_core/TRADING_SUBSYSTEM_DISABLEMENT.md.
# Pedro: the Task Scheduler task itself still fires at 09:15 ET; this script
# is now inert with respect to trading, but you may want to disable/retime
# the scheduled task if TradingView + feed server are no longer needed daily.

$DONNA_DIR = Split-Path $PSScriptRoot -Parent
$PYTHON    = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PYTHON) {
    Write-Host "[ERROR] python not found on PATH" -ForegroundColor Red
    pause
    exit 1
}

# 1. TradingView (CDP mode) — retained for manual chart viewing only; no
#    automation reads or writes this session (monitor.py is not launched below).
Write-Host "[1/2] Starting TradingView with CDP..." -ForegroundColor Cyan

$tvPkg = Get-AppxPackage -Name "*TradingView*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($tvPkg) {
    $tvExe = Join-Path $tvPkg.InstallLocation "TradingView.exe"
} else {
    $tvExe = $null
}

if (-not $tvExe -or -not (Test-Path $tvExe)) {
    Write-Host "[WARN] TradingView not found via AppxPackage - skipping TV launch" -ForegroundColor Yellow
} else {
    Stop-Process -Name "TradingView" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-Process -FilePath $tvExe -ArgumentList "--remote-debugging-port=9222"
    Write-Host "      TradingView launched (CDP port 9222)" -ForegroundColor Green
    Start-Sleep -Seconds 5
}

# Trading subsystem stays retired regardless of what's in the shell/user env —
# do not set NOVA_AUTO_EXECUTE here, and explicitly force the master switch off.
$env:NOVA_TRADING_SUBSYSTEM_ENABLED = 'false'
Write-Host "      NOVA_TRADING_SUBSYSTEM_ENABLED=false (legacy trading subsystem retired)" -ForegroundColor DarkCyan

# 2. Feed server (uvicorn) — market data + headline loops + Journal/Assistant API
Write-Host "[2/2] Starting NOVA feed server (uvicorn)..." -ForegroundColor Cyan

$feedCmd = "cd `"$DONNA_DIR`"; python -m uvicorn main:app --host 0.0.0.0 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $feedCmd -WindowStyle Normal
Start-Sleep -Seconds 3

Write-Host "      Feed server launched (port 8000)" -ForegroundColor Green

# 3. NOVA reasoning monitor — NOT launched. Its only purpose was the retired
#    reasoning -> alert -> execution pipeline; it now exits immediately if run
#    directly (NOVA_TRADING_SUBSYSTEM_ENABLED=false), so there is nothing for
#    this script to gain by starting it.

Write-Host ""
Write-Host "Session ready (trading subsystem retired)." -ForegroundColor Green
Write-Host "  TradingView  : CDP on port 9222 (no consumer while retired)"
Write-Host "  Feed server  : uvicorn on port 8000 (Journal / Market / Assistant / finnhub / headlines)"
Write-Host "  NOVA monitor : NOT started — legacy trading subsystem retired"
Write-Host ""
