# start_dev.ps1 - Скрипт для запуска в dev режиме
# Запустите: .\start_dev.ps1

Write-Host "Starting News Aggregator in development mode..." -ForegroundColor Green

# Активация виртуального окружения
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Запуск инфраструктуры
Write-Host "Starting infrastructure services..." -ForegroundColor Yellow
docker-compose up -d postgres rabbitmq redis

# Ожидание запуска сервисов
Write-Host "Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Проверка доступности сервисов
Write-Host "Checking services health..." -ForegroundColor Yellow

# Проверка PostgreSQL
try {
    $pgTest = docker exec news-postgres pg_isready -U newsuser -d newsdb
    if ($pgTest -match "accepting connections") {
        Write-Host "✅ PostgreSQL is ready" -ForegroundColor Green
    } else {
        Write-Host "❌ PostgreSQL is not ready" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ PostgreSQL check failed" -ForegroundColor Red
}

# Проверка RabbitMQ
try {
    $rmqTest = docker exec news-rabbitmq rabbitmq-diagnostics ping
    if ($rmqTest -match "pong") {
        Write-Host "✅ RabbitMQ is ready" -ForegroundColor Green
    } else {
        Write-Host "❌ RabbitMQ is not ready" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ RabbitMQ check failed" -ForegroundColor Red
}

# Проверка Redis
try {
    $redisTest = docker exec news-redis redis-cli ping
    if ($redisTest -match "PONG") {
        Write-Host "✅ Redis is ready" -ForegroundColor Green
    } else {
        Write-Host "❌ Redis is not ready" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Redis check failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "🚀 Starting application services..." -ForegroundColor Green
Write-Host ""

# Функция для запуска сервиса в новом окне PowerShell
function Start-ServiceInNewWindow {
    param(
        [string]$ServiceName,
        [string]$ScriptPath,
        [string]$Title
    )
    
    $scriptBlock = {
        param($scriptPath, $title)
        Set-Location $PWD
        & "venv\Scripts\Activate.ps1"
        Write-Host "Starting $title..." -ForegroundColor Green
        python $scriptPath
    }
    
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { $($scriptBlock.ToString()) } -scriptPath '$scriptPath' -title '$title'"
}

# Запуск сервисов в отдельных окнах
Write-Host "Starting services in separate windows..." -ForegroundColor Yellow

# API сервер
Start-ServiceInNewWindow -ServiceName "API" -ScriptPath "scripts\start_api.py" -Title "News Aggregator API"

# Telegram_Parser
Start-ServiceInNewWindow -ServiceName "Telegram_Parser" -ScriptPath "scripts\start_telegram_parser.py" -Title "Telegram_Parser"

# Outbox Relay
Start-ServiceInNewWindow -ServiceName "OutboxRelay" -ScriptPath "scripts\start_outbox_relay.py" -Title "Outbox Relay"

Write-Host ""
Write-Host "✅ All services started!" -ForegroundColor Green
Write-Host ""
Write-Host "Services running:"
Write-Host "  📡 API Server: http://localhost:8000" -ForegroundColor Cyan
Write-Host "  📊 API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  🐰 RabbitMQ Management: http://localhost:15672 (admin/admin123)" -ForegroundColor Cyan
Write-Host "  🌐 Neo4j Browser: http://localhost:7474 (neo4j/password123)" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop all services, run: .\stop_dev.ps1" -ForegroundColor Yellow
Write-Host "To view logs, run: .\view_logs.ps1" -ForegroundColor Yellow
