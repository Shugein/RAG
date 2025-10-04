# start_full.ps1 - Скрипт для полного запуска через Docker
# Запустите: .\start_full.ps1

Write-Host "Starting News Aggregator in full Docker mode..." -ForegroundColor Green

# Проверка наличия .env файла
if (!(Test-Path ".env")) {
    Write-Host "❌ .env file not found. Please run .\setup.ps1 first" -ForegroundColor Red
    exit 1
}

# Сборка и запуск всех сервисов
Write-Host "Building and starting all services..." -ForegroundColor Yellow
docker-compose up -d --build

# Ожидание запуска сервисов
Write-Host "Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Проверка статуса сервисов
Write-Host "Checking services status..." -ForegroundColor Yellow
docker-compose ps

Write-Host ""
Write-Host "✅ All services started!" -ForegroundColor Green
Write-Host ""
Write-Host "Services available:"
Write-Host "  📡 API Server: http://localhost:8000" -ForegroundColor Cyan
Write-Host "  📊 API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  🐰 RabbitMQ Management: http://localhost:15672 (admin/admin123)" -ForegroundColor Cyan
Write-Host "  🌐 Neo4j Browser: http://localhost:7474 (neo4j/password123)" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop all services, run: .\stop_full.ps1" -ForegroundColor Yellow
Write-Host "To view logs, run: .\view_logs.ps1" -ForegroundColor Yellow
