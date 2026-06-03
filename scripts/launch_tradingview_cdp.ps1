$tvPkg = Get-AppxPackage -Name "*TradingView*" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $tvPkg) {
    Write-Host "[ERROR] TradingView not found via AppxPackage" -ForegroundColor Red
    exit 1
}
$tvExe = Join-Path $tvPkg.InstallLocation "TradingView.exe"

Stop-Process -Name "TradingView" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Start-Process -FilePath $tvExe -ArgumentList "--remote-debugging-port=9222"
Write-Host "TradingView launched with CDP on port 9222" -ForegroundColor Green
