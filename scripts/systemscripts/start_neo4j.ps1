# start_neo4j.ps1
# Скрипт для запуска Neo4j через Docker

Write-Host "🚀 Запуск Neo4j через Docker..." -ForegroundColor Green

# Проверяем, установлен ли Docker
try {
    $dockerVersion = docker --version
    Write-Host "✅ Docker найден: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker не установлен!" -ForegroundColor Red
    Write-Host "Пожалуйста, установите Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Проверяем, запущен ли уже Neo4j
$existingContainer = docker ps -q --filter "name=neo4j"
if ($existingContainer) {
    Write-Host "⚠️  Neo4j уже запущен (контейнер: $existingContainer)" -ForegroundColor Yellow
    Write-Host "Останавливаем существующий контейнер..." -ForegroundColor Yellow
    docker stop neo4j
    docker rm neo4j
}

# Запускаем Neo4j
Write-Host "🐳 Запуск Neo4j контейнера..." -ForegroundColor Blue
docker run -d `
    --name neo4j `
    -p 7474:7474 `
    -p 7687:7687 `
    -e NEO4J_AUTH=neo4j/password `
    -e NEO4J_PLUGINS=["apoc"] `
    -e NEO4J_dbms_security_procedures_unrestricted=apoc.* `
    neo4j:latest

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Neo4j успешно запущен!" -ForegroundColor Green
    Write-Host ""
    Write-Host "🌐 Neo4j Browser: http://localhost:7474" -ForegroundColor Cyan
    Write-Host "🔌 Bolt URI: bolt://localhost:7687" -ForegroundColor Cyan
    Write-Host "👤 Логин: neo4j" -ForegroundColor Cyan
    Write-Host "🔑 Пароль: password" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "⏳ Ожидание запуска Neo4j (30 секунд)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
    
    Write-Host "🧪 Запуск тестового скрипта..." -ForegroundColor Blue
    python scripts/setup_neo4j.py
    
} else {
    Write-Host "❌ Ошибка запуска Neo4j!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🎉 Готово! Neo4j запущен и настроен." -ForegroundColor Green
Write-Host "Для остановки: docker stop neo4j" -ForegroundColor Yellow
Write-Host "Для удаления: docker rm neo4j" -ForegroundColor Yellow
