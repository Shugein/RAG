# start_ceg_parser.ps1
# Скрипт для запуска CEG парсера с HTML интеграцией

param(
    [switch]$Help,
    [switch]$TelegramOnly,
    [switch]$HTMLOnly
)

if ($Help) {
    Write-Host "CEG Parser Launcher with HTML Integration" -ForegroundColor Green
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\start_ceg_parser.ps1                    # Parse all sources (Telegram + HTML)"
    Write-Host "  .\start_ceg_parser.ps1 -TelegramOnly     # Parse only Telegram sources"
    Write-Host "  .\start_ceg_parser.ps1 -HTMLOnly         # Parse only HTML sources"
    Write-Host ""
    Write-Host "Features:"
    Write-Host "  - Telegram sources with CEG analysis"
    Write-Host "  - HTML sources (Forbes, Interfax) with CEG analysis"
    Write-Host "  - AI-based entity recognition"
    Write-Host "  - Neo4j graph database integration"
    Write-Host "  - Batch processing and real-time monitoring"
    exit 0
}

# Проверяем виртуальное окружение
if (-not (Test-Path "venv\Scripts\activate.ps1")) {
    Write-Host "Virtual environment not found. Please run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Активируем виртуальное окружение
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\activate.ps1"

# Проверяем наличие Python
$pythonPath = "venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    Write-Host "Python not found in virtual environment." -ForegroundColor Red
    exit 1
}

# Выводим информацию о запуске
Write-Host "Starting CEG Parser with HTML Integration..." -ForegroundColor Green

if ($TelegramOnly) {
    Write-Host "  Mode: Telegram sources only" -ForegroundColor Cyan
} elseif ($HTMLOnly) {
    Write-Host "  Mode: HTML sources only" -ForegroundColor Cyan
} else {
    Write-Host "  Mode: All sources (Telegram + HTML)" -ForegroundColor Cyan
}

Write-Host "  Features: CEG analysis, AI NER, Neo4j graph, Batch processing" -ForegroundColor Cyan
Write-Host ""

# Проверяем наличие конфигурации источников
if (-not (Test-Path "config\sources.yml")) {
    Write-Host "Sources configuration not found. Please run setup first." -ForegroundColor Red
    exit 1
}

# Проверяем наличие БД
Write-Host "Checking database connection..." -ForegroundColor Yellow
try {
    & $pythonPath -c "
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.')))
from src.core.database import init_db, close_db
async def check_db():
    await init_db()
    print('Database connection: OK')
    await close_db()
asyncio.run(check_db())
" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Database connection failed. Please check your database configuration." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Database connection failed. Please check your database configuration." -ForegroundColor Red
    exit 1
}

Write-Host "Database connection: OK" -ForegroundColor Green

# Запускаем CEG парсер
try {
    Write-Host ""
    Write-Host "🚀 Launching CEG Parser..." -ForegroundColor Green
    
    if ($TelegramOnly) {
        Write-Host "   📡 Processing Telegram sources only" -ForegroundColor Cyan
    } elseif ($HTMLOnly) {
        Write-Host "   🌐 Processing HTML sources only" -ForegroundColor Cyan
    } else {
        Write-Host "   📡 Processing Telegram sources" -ForegroundColor Cyan
        Write-Host "   🌐 Processing HTML sources (Forbes, Interfax)" -ForegroundColor Cyan
    }
    
    Write-Host ""
    
    & $pythonPath "scripts\start_telegram_parser_ceg.py"
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {
        Write-Host ""
        Write-Host "✅ CEG Parser completed successfully!" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "❌ CEG Parser failed with exit code: $exitCode" -ForegroundColor Red
    }
    
    exit $exitCode
    
} catch {
    Write-Host ""
    Write-Host "❌ Error running CEG Parser: $_" -ForegroundColor Red
    exit 1
}
