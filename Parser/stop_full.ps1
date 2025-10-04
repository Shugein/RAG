# stop_full.ps1 - Скрипт для остановки полного режима
# Запустите: .\stop_full.ps1

Write-Host "Stopping News Aggregator full mode..." -ForegroundColor Yellow

# Остановка всех Docker контейнеров
Write-Host "Stopping all Docker containers..." -ForegroundColor Yellow
docker-compose down

# Опционально: удаление volumes (раскомментируйте если нужно)
# Write-Host "Removing volumes..." -ForegroundColor Yellow
# docker-compose down -v

Write-Host "✅ All services stopped!" -ForegroundColor Green
