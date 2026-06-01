# start_trading_session.ps1
# Starts TradingView (CDP mode) + NOVA local monitor in a dedicated window.
# Run this once before the session opens.

$DONNA_DIR = Split-Path $PSScriptRoot -Parent
$PYTHON    = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PYTHON) {
    Write-Host "[ERROR] python not found on PATH" -ForegroundColor Red
    pause
    exit 1
}

# 1. TradingView (CDP mode)
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

# 2. NOVA monitor in its own persistent terminal window
Write-Host "[2/2] Starting NOVA monitor..." -ForegroundColor Cyan

$monitorScript = Join-Path $DONNA_DIR "donna_local_monitor.py"
$cmd = "cd `"$DONNA_DIR`"; python `"$monitorScript`""

Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal

Write-Host ""
Write-Host "Session ready." -ForegroundColor Green
Write-Host "  TradingView : CDP on port 9222"
Write-Host "  NOVA monitor: running in separate window (09:30-11:00 ET)"
Write-Host ""
Write-Host "Close the NOVA window to stop the monitor."
