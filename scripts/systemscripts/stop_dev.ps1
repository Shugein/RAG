# stop_dev.ps1 - Скрипт для остановки dev сервисов
# Запустите: .\stop_dev.ps1

Write-Host "Stopping News Aggregator services..." -ForegroundColor Yellow

# Остановка Docker контейнеров
Write-Host "Stopping Docker containers..." -ForegroundColor Yellow
docker-compose down

# Остановка всех Python процессов (если они запущены в текущей сессии)
Write-Host "Stopping Python services..." -ForegroundColor Yellow
$pythonProcesses = Get-Process | Where-Object { $_.ProcessName -eq "python" -and $_.MainWindowTitle -match "(API|Parser|Relay)" }
if ($pythonProcesses) {
    $pythonProcesses | Stop-Process -Force
    Write-Host "Stopped Python services" -ForegroundColor Green
} else {
    Write-Host "No Python services found running in current session" -ForegroundColor Yellow
}

Write-Host "✅ All services stopped!" -ForegroundColor Green
