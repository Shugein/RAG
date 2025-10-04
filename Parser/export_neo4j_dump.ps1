# export_neo4j_dump.ps1
# PowerShell скрипт для выгрузки дампа Neo4j

param(
    [string]$Format = "all",  # all, cypher, json, csv
    [string]$OutputDir = "dumps",
    [switch]$Help
)

if ($Help) {
    Write-Host "Экспорт дампа базы данных Neo4j" -ForegroundColor Green
    Write-Host ""
    Write-Host "Использование:" -ForegroundColor Yellow
    Write-Host "  .\export_neo4j_dump.ps1 [-Format <format>] [-OutputDir <dir>] [-Help]"
    Write-Host ""
    Write-Host "Параметры:" -ForegroundColor Yellow
    Write-Host "  -Format     Формат экспорта: all, cypher, json, csv (по умолчанию: all)"
    Write-Host "  -OutputDir  Директория для сохранения дампов (по умолчанию: dumps)"
    Write-Host "  -Help       Показать эту справку"
    Write-Host ""
    Write-Host "Примеры:" -ForegroundColor Yellow
    Write-Host "  .\export_neo4j_dump.ps1"
    Write-Host "  .\export_neo4j_dump.ps1 -Format cypher"
    Write-Host "  .\export_neo4j_dump.ps1 -OutputDir C:\backups"
    exit 0
}

Write-Host "🚀 Экспорт дампа Neo4j" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green

# Проверяем, что Neo4j запущен
Write-Host "🔍 Проверка подключения к Neo4j..." -ForegroundColor Yellow

try {
    $neo4jStatus = docker ps --filter "name=radar-neo4j" --format "table {{.Status}}" | Select-String "Up"
    if (-not $neo4jStatus) {
        Write-Host "❌ Neo4j не запущен. Запускаем..." -ForegroundColor Red
        docker-compose up -d neo4j
        Start-Sleep -Seconds 10
    } else {
        Write-Host "✅ Neo4j запущен" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Ошибка проверки статуса Neo4j: $_" -ForegroundColor Red
    Write-Host "💡 Убедитесь, что Docker запущен" -ForegroundColor Yellow
    exit 1
}

# Активируем виртуальное окружение
Write-Host "🐍 Активация виртуального окружения..." -ForegroundColor Yellow
if (Test-Path "venv\Scripts\Activate.ps1") {
    & "venv\Scripts\Activate.ps1"
    Write-Host "✅ Виртуальное окружение активировано" -ForegroundColor Green
} else {
    Write-Host "❌ Виртуальное окружение не найдено" -ForegroundColor Red
    Write-Host "💡 Сначала выполните: .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

# Создаем директорию для дампов
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    Write-Host "📁 Создана директория: $OutputDir" -ForegroundColor Green
}

# Запускаем экспорт
Write-Host "📤 Запуск экспорта дампа..." -ForegroundColor Yellow

try {
    $pythonScript = "scripts\export_neo4j_dump.py"
    
    if (Test-Path $pythonScript) {
        python $pythonScript
        $exitCode = $LASTEXITCODE
        
        if ($exitCode -eq 0) {
            Write-Host "✅ Экспорт завершен успешно!" -ForegroundColor Green
            
            # Показываем созданные файлы
            Write-Host "`n📁 Созданные файлы:" -ForegroundColor Yellow
            Get-ChildItem -Path $OutputDir -Recurse | Where-Object { $_.Name -like "*neo4j_dump*" } | ForEach-Object {
                $size = [math]::Round($_.Length / 1MB, 2)
                Write-Host "  $($_.FullName) ($size MB)" -ForegroundColor Cyan
            }
            
            Write-Host "`n💡 Для восстановления дампа используйте:" -ForegroundColor Yellow
            Write-Host "   cypher-shell -u neo4j -p password123 \`< dumps\neo4j_dump_*.cypher" -ForegroundColor Cyan
            
        } else {
            Write-Host "❌ Ошибка экспорта (код: $exitCode)" -ForegroundColor Red
        }
    } else {
        Write-Host "❌ Скрипт экспорта не найден: $pythonScript" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ Ошибка выполнения: $_" -ForegroundColor Red
}

Write-Host "`nГотово!" -ForegroundColor Green
