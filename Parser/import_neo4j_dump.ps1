# import_neo4j_dump.ps1
# PowerShell скрипт для восстановления дампа Neo4j

param(
    [Parameter(Mandatory=$true)]
    [string]$DumpFile,  # Путь к файлу дампа
    [switch]$Clear,     # Очистить базу данных перед импортом
    [switch]$Verify,    # Проверить импорт после завершения
    [switch]$Help
)

if ($Help) {
    Write-Host "Восстановление дампа базы данных Neo4j" -ForegroundColor Green
    Write-Host ""
    Write-Host "Использование:" -ForegroundColor Yellow
    Write-Host "  .\import_neo4j_dump.ps1 -DumpFile <path> [-Clear] [-Verify] [-Help]"
    Write-Host ""
    Write-Host "Параметры:" -ForegroundColor Yellow
    Write-Host "  -DumpFile   Путь к файлу дампа (.cypher, .json) или директории с CSV файлами"
    Write-Host "  -Clear      Очистить базу данных перед импортом"
    Write-Host "  -Verify     Проверить импорт после завершения"
    Write-Host "  -Help       Показать эту справку"
    Write-Host ""
    Write-Host "Примеры:" -ForegroundColor Yellow
    Write-Host "  .\import_neo4j_dump.ps1 -DumpFile dumps\neo4j_dump_20241203_143022.cypher"
    Write-Host "  .\import_neo4j_dump.ps1 -DumpFile dumps\neo4j_dump_20241203_143022.json -Clear"
    Write-Host "  .\import_neo4j_dump.ps1 -DumpFile dumps\neo4j_dump_20241203_143022_csv -Verify"
    exit 0
}

Write-Host "🚀 Восстановление дампа Neo4j" -ForegroundColor Green
Write-Host "=============================" -ForegroundColor Green

# Проверяем, что файл дампа существует
if (-not (Test-Path $DumpFile)) {
    Write-Host "❌ Файл дампа не найден: $DumpFile" -ForegroundColor Red
    exit 1
}

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

# Предупреждение о очистке базы данных
if ($Clear) {
    Write-Host "⚠️  ВНИМАНИЕ: База данных будет полностью очищена!" -ForegroundColor Red
    $confirm = Read-Host "Продолжить? (y/N)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "❌ Импорт отменен" -ForegroundColor Yellow
        exit 0
    }
}

# Запускаем импорт
Write-Host "📥 Запуск импорта дампа..." -ForegroundColor Yellow

try {
    $pythonScript = "scripts\import_neo4j_dump.py"
    
    if (Test-Path $pythonScript) {
        $args = @($DumpFile)
        if ($Clear) { $args += "--clear" }
        if ($Verify) { $args += "--verify" }
        
        python $pythonScript @args
        $exitCode = $LASTEXITCODE
        
        if ($exitCode -eq 0) {
            Write-Host "✅ Импорт завершен успешно!" -ForegroundColor Green
            
            if ($Verify) {
                Write-Host "`n📊 Статистика импорта:" -ForegroundColor Yellow
                Write-Host "  Проверьте Neo4j Browser: http://localhost:7474" -ForegroundColor Cyan
                Write-Host "  Логин: neo4j" -ForegroundColor Cyan
                Write-Host "  Пароль: password123" -ForegroundColor Cyan
            }
            
        } else {
            Write-Host "❌ Ошибка импорта (код: $exitCode)" -ForegroundColor Red
        }
    } else {
        Write-Host "❌ Скрипт импорта не найден: $pythonScript" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ Ошибка выполнения: $_" -ForegroundColor Red
}

Write-Host "`n🏁 Готово!" -ForegroundColor Green
