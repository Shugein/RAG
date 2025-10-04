# reset_project.ps1 - Скрипт для сброса проекта
# Запустите: .\reset_project.ps1

Write-Host "🔄 Resetting News Aggregator Project" -ForegroundColor Yellow
Write-Host "====================================" -ForegroundColor Yellow
Write-Host ""

# Предупреждение
Write-Host "⚠️  ВНИМАНИЕ: Этот скрипт удалит:" -ForegroundColor Red
Write-Host "   - Все Docker контейнеры и volumes" -ForegroundColor Red
Write-Host "   - Виртуальное окружение Python" -ForegroundColor Red
Write-Host "   - Сессии Telegram" -ForegroundColor Red
Write-Host "   - Логи и временные файлы" -ForegroundColor Red
Write-Host ""

$confirm = Read-Host "Вы уверены? Введите 'yes' для подтверждения"
if ($confirm -ne "yes") {
    Write-Host "❌ Операция отменена" -ForegroundColor Yellow
    exit 0
}

Write-Host "🛑 Остановка всех сервисов..." -ForegroundColor Yellow

# Остановка Docker контейнеров
try {
    docker-compose down -v 2>$null
    Write-Host "✅ Docker контейнеры остановлены" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Ошибка при остановке Docker контейнеров" -ForegroundColor Yellow
}

# Удаление Docker volumes
try {
    docker volume prune -f 2>$null
    Write-Host "✅ Docker volumes очищены" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Ошибка при очистке Docker volumes" -ForegroundColor Yellow
}

Write-Host "🗑️  Удаление файлов..." -ForegroundColor Yellow

# Удаление виртуального окружения
if (Test-Path "venv") {
    Remove-Item -Recurse -Force "venv"
    Write-Host "✅ Виртуальное окружение удалено" -ForegroundColor Green
}

# Удаление сессий Telegram
if (Test-Path "sessions") {
    Remove-Item -Recurse -Force "sessions"
    Write-Host "✅ Сессии Telegram удалены" -ForegroundColor Green
}

# Удаление __pycache__
Get-ChildItem -Path . -Recurse -Name "__pycache__" | ForEach-Object {
    Remove-Item -Recurse -Force $_
}
Write-Host "✅ Python кэш очищен" -ForegroundColor Green

# Удаление .pyc файлов
Get-ChildItem -Path . -Recurse -Name "*.pyc" | ForEach-Object {
    Remove-Item -Force $_
}
Write-Host "✅ .pyc файлы удалены" -ForegroundColor Green

# Удаление логов
if (Test-Path "logs") {
    Remove-Item -Recurse -Force "logs"
    Write-Host "✅ Логи удалены" -ForegroundColor Green
}

# Удаление временных файлов
Get-ChildItem -Path . -Recurse -Name "*.tmp" | ForEach-Object {
    Remove-Item -Force $_
}
Get-ChildItem -Path . -Recurse -Name "*.log" | ForEach-Object {
    Remove-Item -Force $_
}
Write-Host "✅ Временные файлы удалены" -ForegroundColor Green

Write-Host ""
Write-Host "✅ Проект сброшен!" -ForegroundColor Green
Write-Host ""
Write-Host "Для повторной установки запустите:" -ForegroundColor Yellow
Write-Host "  .\setup.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "Или для быстрого старта:" -ForegroundColor Yellow
Write-Host "  .\setup.ps1 && .\start_dev.ps1" -ForegroundColor Cyan
