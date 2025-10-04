# check_health.ps1 - Скрипт для проверки здоровья системы
# Запустите: .\check_health.ps1

Write-Host "🔍 Checking News Aggregator Health..." -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""

# Функция для проверки HTTP эндпоинта
function Test-HttpEndpoint {
    param(
        [string]$Url,
        [string]$ServiceName
    )
    
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ $ServiceName is healthy" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ $ServiceName returned status: $($response.StatusCode)" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ $ServiceName is not responding: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Функция для проверки Docker контейнера
function Test-DockerContainer {
    param(
        [string]$ContainerName,
        [string]$ServiceName
    )
    
    try {
        $container = docker ps --filter "name=$ContainerName" --format "table {{.Status}}"
        if ($container -match "Up") {
            Write-Host "✅ $ServiceName container is running" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ $ServiceName container is not running" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ $ServiceName container check failed" -ForegroundColor Red
        return $false
    }
}

# Проверка Docker контейнеров
Write-Host "🐳 Docker Containers:" -ForegroundColor Cyan
Test-DockerContainer -ContainerName "news-postgres" -ServiceName "PostgreSQL"
Test-DockerContainer -ContainerName "news-rabbitmq" -ServiceName "RabbitMQ"
Test-DockerContainer -ContainerName "news-redis" -ServiceName "Redis"
Test-DockerContainer -ContainerName "news-api" -ServiceName "API Server"
Test-DockerContainer -ContainerName "news-telegram-parser" -ServiceName "Telegram Parser"
Test-DockerContainer -ContainerName "news-outbox-relay" -ServiceName "Outbox Relay"
Test-DockerContainer -ContainerName "news-enricher" -ServiceName "Enricher"

Write-Host ""

# Проверка HTTP эндпоинтов
Write-Host "🌐 HTTP Endpoints:" -ForegroundColor Cyan
Test-HttpEndpoint -Url "http://localhost:8000/health" -ServiceName "API Health"
Test-HttpEndpoint -Url "http://localhost:15672" -ServiceName "RabbitMQ Management"
Test-HttpEndpoint -Url "http://localhost:7474" -ServiceName "Neo4j Browser"

Write-Host ""

# Проверка подключения к базе данных
Write-Host "🗄️ Database Connection:" -ForegroundColor Cyan
try {
    $dbTest = docker exec news-postgres psql -U newsuser -d newsdb -c "SELECT 1;" 2>$null
    if ($dbTest -match "1") {
        Write-Host "✅ Database connection successful" -ForegroundColor Green
    } else {
        Write-Host "❌ Database connection failed" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Database connection test failed" -ForegroundColor Red
}

Write-Host ""

# Проверка RabbitMQ
Write-Host "🐰 RabbitMQ Status:" -ForegroundColor Cyan
try {
    $rmqTest = docker exec news-rabbitmq rabbitmq-diagnostics ping
    if ($rmqTest -match "pong") {
        Write-Host "✅ RabbitMQ is responding" -ForegroundColor Green
    } else {
        Write-Host "❌ RabbitMQ is not responding" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ RabbitMQ check failed" -ForegroundColor Red
}

Write-Host ""

# Проверка Redis
Write-Host "🔴 Redis Status:" -ForegroundColor Cyan
try {
    $redisTest = docker exec news-redis redis-cli ping
    if ($redisTest -match "PONG") {
        Write-Host "✅ Redis is responding" -ForegroundColor Green
    } else {
        Write-Host "❌ Redis is not responding" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Redis check failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "Health check completed!" -ForegroundColor Green
