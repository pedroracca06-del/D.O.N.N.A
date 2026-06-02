# start_trading_session.ps1
# Starts TradingView (CDP mode) + NOVA feed server + NOVA local monitor.
# Triggered automatically by Task Scheduler at 09:15 ET Mon-Fri.

$DONNA_DIR = Split-Path $PSScriptRoot -Parent
$PYTHON    = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PYTHON) {
    Write-Host "[ERROR] python not found on PATH" -ForegroundColor Red
    pause
    exit 1
}

# 1. TradingView (CDP mode)
Write-Host "[1/3] Starting TradingView with CDP..." -ForegroundColor Cyan

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

# Enable auto-execution bridge (paper mode only — bridge enforces this internally)
$env:NOVA_AUTO_EXECUTE = 'true'
Write-Host "      NOVA_AUTO_EXECUTE=true (paper mode)" -ForegroundColor DarkCyan

# 2. Feed server (uvicorn) — market data + headline loops
Write-Host "[2/3] Starting NOVA feed server (uvicorn)..." -ForegroundColor Cyan

$feedCmd = "cd `"$DONNA_DIR`"; python -m uvicorn main:app --host 0.0.0.0 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $feedCmd -WindowStyle Normal
Start-Sleep -Seconds 3

Write-Host "      Feed server launched (port 8000)" -ForegroundColor Green

# 3. NOVA reasoning monitor
Write-Host "[3/3] Starting NOVA reasoning monitor..." -ForegroundColor Cyan

$monitorScript = Join-Path $DONNA_DIR "donna_local_monitor.py"
$monitorCmd = "cd `"$DONNA_DIR`"; python `"$monitorScript`""
Start-Process powershell -ArgumentList "-NoExit", "-Command", $monitorCmd -WindowStyle Normal

Write-Host ""
Write-Host "Session ready." -ForegroundColor Green
Write-Host "  TradingView  : CDP on port 9222"
Write-Host "  Feed server  : uvicorn on port 8000 (finnhub + headlines every 5-15 min)"
Write-Host "  NOVA monitor : reasoning cycle every 60s, Discord alerts active"
Write-Host ""
