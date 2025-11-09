# stop_neo4j.ps1
# Скрипт для остановки Neo4j

Write-Host "🛑 Остановка Neo4j..." -ForegroundColor Yellow

# Проверяем, запущен ли Neo4j
$existingContainer = docker ps -q --filter "name=neo4j"
if ($existingContainer) {
    Write-Host "⏹️  Останавливаем контейнер Neo4j..." -ForegroundColor Blue
    docker stop neo4j
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Neo4j остановлен!" -ForegroundColor Green
    } else {
        Write-Host "❌ Ошибка остановки Neo4j!" -ForegroundColor Red
    }
} else {
    Write-Host "ℹ️  Neo4j не запущен" -ForegroundColor Blue
}

# Удаляем контейнер
Write-Host "🗑️  Удаляем контейнер..." -ForegroundColor Blue
docker rm neo4j 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Контейнер удален!" -ForegroundColor Green
} else {
    Write-Host "ℹ️  Контейнер не найден или уже удален" -ForegroundColor Blue
}

Write-Host "🎉 Готово!" -ForegroundColor Green
