# setup_telegram.ps1 - Скрипт для настройки Telegram API
# Запустите: .\setup_telegram.ps1

Write-Host "🔧 Telegram API Setup" -ForegroundColor Green
Write-Host "====================" -ForegroundColor Green
Write-Host ""

# Проверка наличия .env файла
if (!(Test-Path ".env")) {
    Write-Host "❌ .env file not found. Please run .\setup.ps1 first" -ForegroundColor Red
    exit 1
}

Write-Host "Для настройки Telegram API вам нужно:" -ForegroundColor Yellow
Write-Host "1. Перейти на https://my.telegram.org" -ForegroundColor Cyan
Write-Host "2. Войти в свой аккаунт Telegram" -ForegroundColor Cyan
Write-Host "3. Перейти в 'API development tools'" -ForegroundColor Cyan
Write-Host "4. Создать новое приложение" -ForegroundColor Cyan
Write-Host ""

# Запрос API ID
$apiId = Read-Host "Введите API ID"
if ([string]::IsNullOrWhiteSpace($apiId)) {
    Write-Host "❌ API ID не может быть пустым" -ForegroundColor Red
    exit 1
}

# Запрос API Hash
$apiHash = Read-Host "Введите API Hash"
if ([string]::IsNullOrWhiteSpace($apiHash)) {
    Write-Host "❌ API Hash не может быть пустым" -ForegroundColor Red
    exit 1
}

# Запрос номера телефона
$phone = Read-Host "Введите номер телефона (например: +79999999999)"
if ([string]::IsNullOrWhiteSpace($phone)) {
    Write-Host "❌ Номер телефона не может быть пустым" -ForegroundColor Red
    exit 1
}

# Обновление .env файла
Write-Host "Обновление .env файла..." -ForegroundColor Yellow

$envContent = Get-Content ".env" -Raw
$envContent = $envContent -replace "TELETHON_API_ID=.*", "TELETHON_API_ID=$apiId"
$envContent = $envContent -replace "TELETHON_API_HASH=.*", "TELETHON_API_HASH=$apiHash"
$envContent = $envContent -replace "TELETHON_PHONE=.*", "TELETHON_PHONE=$phone"

$envContent | Out-File -FilePath ".env" -Encoding UTF8

Write-Host "✅ Telegram API настроен!" -ForegroundColor Green
Write-Host ""
Write-Host "Теперь вы можете запустить проект:" -ForegroundColor Yellow
Write-Host "  .\start_dev.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "При первом запуске Telegram парсера вам будет предложено:" -ForegroundColor Yellow
Write-Host "1. Ввести код подтверждения из SMS" -ForegroundColor Cyan
Write-Host "2. Ввести пароль двухфакторной аутентификации (если включена)" -ForegroundColor Cyan
