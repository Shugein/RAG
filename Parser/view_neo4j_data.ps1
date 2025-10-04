# view_neo4j_data.ps1
# Скрипт для просмотра данных в Neo4j

Write-Host "🔍 Просмотр данных в Neo4j..." -ForegroundColor Green

# Проверяем, запущен ли Neo4j
$existingContainer = docker ps -q --filter "name=neo4j"
if (-not $existingContainer) {
    Write-Host "❌ Neo4j не запущен!" -ForegroundColor Red
    Write-Host "Запустите сначала: .\start_neo4j.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Neo4j запущен" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Открываем Neo4j Browser..." -ForegroundColor Blue
Write-Host "   URL: http://localhost:7474" -ForegroundColor Cyan
Write-Host "   Логин: neo4j" -ForegroundColor Cyan
Write-Host "   Пароль: password" -ForegroundColor Cyan
Write-Host ""

# Открываем браузер
Start-Process "http://localhost:7474"

Write-Host "📋 Полезные запросы для Neo4j Browser:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Все узлы и связи:" -ForegroundColor White
Write-Host "   MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 10" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Статистика узлов:" -ForegroundColor White
Write-Host "   MATCH (n) RETURN labels(n) as node_type, count(n) as count ORDER BY count DESC" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Статистика связей:" -ForegroundColor White
Write-Host "   MATCH ()-[r]->() RETURN type(r) as relationship_type, count(r) as count ORDER BY count DESC" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Новости по секторам:" -ForegroundColor White
Write-Host "   MATCH (n:News)-[:ABOUT_SECTOR]->(s:Sector) RETURN s.name as sector, count(n) as news_count ORDER BY news_count DESC" -ForegroundColor Gray
Write-Host ""
Write-Host "5. Новости по странам:" -ForegroundColor White
Write-Host "   MATCH (n:News)-[:ABOUT_COUNTRY]->(c:Country) RETURN c.name as country, count(n) as news_count ORDER BY news_count DESC" -ForegroundColor Gray
Write-Host ""
Write-Host "6. Компании по секторам:" -ForegroundColor White
Write-Host "   MATCH (comp:Company)-[:BELONGS_TO]->(s:Sector) RETURN s.name as sector, collect(comp.name) as companies ORDER BY size(companies) DESC" -ForegroundColor Gray
Write-Host ""

Write-Host "🧪 Запуск тестового скрипта..." -ForegroundColor Blue
python scripts/setup_neo4j.py
