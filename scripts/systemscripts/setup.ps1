# setup.ps1 - Скрипт установки для PowerShell
# Запустите: .\setup.ps1

Write-Host "🚀 News Aggregator Setup Script" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green

# Проверка версии Python
Write-Host "Checking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python 3\.(10|11|12)") {
        Write-Host "Using Python: $pythonVersion" -ForegroundColor Green
    } else {
        Write-Host "Python 3.10+ required. Found: $pythonVersion" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Python not found. Please install Python 3.10+" -ForegroundColor Red
    exit 1
}

# Проверка Docker
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    docker --version | Out-Null
    Write-Host "Docker found: $(docker --version)" -ForegroundColor Green
} catch {
    Write-Host "Docker not found. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

try {
    docker-compose --version | Out-Null
    Write-Host "Docker Compose found: $(docker-compose --version)" -ForegroundColor Green
} catch {
    Write-Host "docker-compose not found. Please install Docker Compose first." -ForegroundColor Red
    exit 1
}

# Создание структуры проекта
Write-Host "Creating project structure..." -ForegroundColor Yellow
$directories = @(
    "src\api\endpoints",
    "src\core",
    "src\services\telegram_parser",
    "src\services\enricher",
    "src\services\outbox",
    "src\services\storage",
    "src\utils",
    "config",
    "scripts",
    "docker",
    "migrations\versions",
    "tests\fixtures",
    "sessions",
    "models"
)

foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

# Создание __init__.py файлов
$initFiles = @(
    "src\__init__.py",
    "src\api\__init__.py",
    "src\api\endpoints\__init__.py",
    "src\core\__init__.py",
    "src\services\__init__.py",
    "src\services\telegram_parser\__init__.py",
    "src\services\enricher\__init__.py",
    "src\services\outbox\__init__.py",
    "src\services\storage\__init__.py",
    "src\utils\__init__.py"
)

foreach ($file in $initFiles) {
    if (!(Test-Path $file)) {
        New-Item -ItemType File -Path $file -Force | Out-Null
    }
}

Write-Host "Project structure created" -ForegroundColor Green

# Создание виртуального окружения
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
if (!(Test-Path "venv")) {
    python -m venv venv
}

# Активация виртуального окружения
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Обновление pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Установка зависимостей
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Создание .env файла если не существует
if (!(Test-Path ".env")) {
    Write-Host "Creating .env file..." -ForegroundColor Yellow
    $envContent = @"
# Database
DATABASE_URL=postgresql+asyncpg://newsuser:newspass@localhost:5432/newsdb

# RabbitMQ
RABBITMQ_URL=amqp://admin:admin123@localhost:5672/

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram (get from https://my.telegram.org)
TELETHON_API_ID=YOUR_API_ID
TELETHON_API_HASH=YOUR_API_HASH
TELETHON_SESSION_NAME=news_parser
TELETHON_PHONE=+79999999999

# Algopack API
ALGOPACK_API_KEY=YOUR_ALGOPACK_KEY
ALGOPACK_BASE_URL=https://api.algopack.com/v1

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
"@
    $envContent | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "Please edit .env file and add your credentials!" -ForegroundColor Red
}

# Запуск инфраструктуры
Write-Host "Starting infrastructure services..." -ForegroundColor Yellow
docker-compose up -d postgres rabbitmq redis

Write-Host "Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Инициализация базы данных
Write-Host "Initializing database..." -ForegroundColor Yellow
if (Test-Path "alembic.ini") {
    # Обновление alembic.ini
    $alembicContent = Get-Content "alembic.ini" -Raw
    $alembicContent = $alembicContent -replace "sqlalchemy\.url = .*", "sqlalchemy.url = postgresql://newsuser:newspass@localhost:5432/newsdb"
    $alembicContent | Out-File -FilePath "alembic.ini" -Encoding UTF8

    # Создание миграций
    Write-Host "Creating database migrations..." -ForegroundColor Yellow
    alembic revision --autogenerate -m "Initial migration" 2>$null
    alembic upgrade head
}

Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Edit .env file with your Telegram and Algopack credentials"
Write-Host "2. Run: .\start_dev.ps1"
Write-Host ""
Write-Host "For full system start:"
Write-Host "  docker-compose up -d"
Write-Host ""
Write-Host "API documentation will be available at:"
Write-Host "  http://localhost:8000/docs"
