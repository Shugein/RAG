# start_html_parser.ps1
# Скрипт для запуска HTML парсеров

param(
    [string]$Source = "",
    [int]$MaxArticles = 50,
    [switch]$LocalAI,
    [switch]$Help
)

if ($Help) {
    Write-Host "HTML Parser Launcher" -ForegroundColor Green
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\start_html_parser.ps1                    # Parse all sources"
    Write-Host "  .\start_html_parser.ps1 -Source forbes     # Parse specific source"
    Write-Host "  .\start_html_parser.ps1 -MaxArticles 100   # Set max articles per source"
    Write-Host "  .\start_html_parser.ps1 -LocalAI           # Use local AI instead of OpenAI"
    Write-Host ""
    Write-Host "Available sources: forbes, interfax"
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

# Формируем команду
$command = "scripts\start_html_parser.py"
$args = @()

if ($Source) {
    $args += "--source"
    $args += $Source
}

if ($MaxArticles -ne 50) {
    $args += "--max-articles"
    $args += $MaxArticles.ToString()
}

if ($LocalAI) {
    $args += "--local-ai"
}

# Выводим информацию о запуске
Write-Host "Starting HTML Parser..." -ForegroundColor Green
if ($Source) {
    Write-Host "  Source: $Source" -ForegroundColor Cyan
} else {
    Write-Host "  Source: All enabled HTML sources" -ForegroundColor Cyan
}
Write-Host "  Max articles per source: $MaxArticles" -ForegroundColor Cyan
Write-Host "  AI mode: $(if ($LocalAI) { 'Local' } else { 'OpenAI API' })" -ForegroundColor Cyan
Write-Host ""

# Запускаем скрипт
try {
    & $pythonPath $command @args
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {
        Write-Host "HTML Parser completed successfully!" -ForegroundColor Green
    } else {
        Write-Host "HTML Parser failed with exit code: $exitCode" -ForegroundColor Red
    }
    
    exit $exitCode
    
} catch {
    Write-Host "Error running HTML Parser: $_" -ForegroundColor Red
    exit 1
}
