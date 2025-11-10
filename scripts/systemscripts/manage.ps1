# manage.ps1 - Главный скрипт управления проектом
# Запустите: .\manage.ps1

param(
    [string]$Action = "menu"
)

function Show-Menu {
    Write-Host ""
    Write-Host "🎯 News Aggregator - Главное меню" -ForegroundColor Green
    Write-Host "=================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "📦 Установка и настройка:" -ForegroundColor Cyan
    Write-Host "  1. Установка проекта" -ForegroundColor White
    Write-Host "  2. Настройка Telegram API" -ForegroundColor White
    Write-Host "  3. Сброс проекта" -ForegroundColor White
    Write-Host ""
    Write-Host "🚀 Запуск сервисов:" -ForegroundColor Cyan
    Write-Host "  4. Запуск в режиме разработки" -ForegroundColor White
    Write-Host "  5. Запуск в полном режиме (Docker)" -ForegroundColor White
    Write-Host ""
    Write-Host "🛑 Остановка сервисов:" -ForegroundColor Cyan
    Write-Host "  6. Остановка режима разработки" -ForegroundColor White
    Write-Host "  7. Остановка полного режима" -ForegroundColor White
    Write-Host ""
    Write-Host "📊 Мониторинг и диагностика:" -ForegroundColor Cyan
    Write-Host "  8. Проверка здоровья системы" -ForegroundColor White
    Write-Host "  9. Просмотр логов" -ForegroundColor White
    Write-Host "  10. Статус Docker контейнеров" -ForegroundColor White
    Write-Host ""
    Write-Host "🔧 Утилиты:" -ForegroundColor Cyan
    Write-Host "  11. Загрузка источников" -ForegroundColor White
    Write-Host "  12. Создание миграции БД" -ForegroundColor White
    Write-Host "  13. Применение миграций БД" -ForegroundColor White
    Write-Host ""
    Write-Host "  0. Выход" -ForegroundColor Red
    Write-Host ""
}

function Invoke-Action {
    param([string]$action)
    
    switch ($action) {
        "1" {
            Write-Host "🔧 Установка проекта..." -ForegroundColor Yellow
            & ".\setup.ps1"
        }
        "2" {
            Write-Host "📱 Настройка Telegram API..." -ForegroundColor Yellow
            & ".\setup_telegram.ps1"
        }
        "3" {
            Write-Host "🔄 Сброс проекта..." -ForegroundColor Yellow
            & ".\reset_project.ps1"
        }
        "4" {
            Write-Host "🚀 Запуск в режиме разработки..." -ForegroundColor Yellow
            & ".\start_dev.ps1"
        }
        "5" {
            Write-Host "🐳 Запуск в полном режиме..." -ForegroundColor Yellow
            & ".\start_full.ps1"
        }
        "6" {
            Write-Host "🛑 Остановка режима разработки..." -ForegroundColor Yellow
            & ".\stop_dev.ps1"
        }
        "7" {
            Write-Host "🛑 Остановка полного режима..." -ForegroundColor Yellow
            & ".\stop_full.ps1"
        }
        "8" {
            Write-Host "🔍 Проверка здоровья системы..." -ForegroundColor Yellow
            & ".\check_health.ps1"
        }
        "9" {
            Write-Host "📋 Просмотр логов..." -ForegroundColor Yellow
            $service = Read-Host "Введите имя сервиса (api, telegram, outbox, all) или нажмите Enter для всех"
            if ([string]::IsNullOrWhiteSpace($service)) {
                $service = "all"
            }
            & ".\view_logs.ps1" -Service $service
        }
        "10" {
            Write-Host "🐳 Статус Docker контейнеров..." -ForegroundColor Yellow
            docker-compose ps
        }
        "11" {
            Write-Host "📥 Загрузка источников..." -ForegroundColor Yellow
            & ".\venv\Scripts\Activate.ps1"
            python scripts\load_sources.py
        }
        "12" {
            Write-Host "📝 Создание миграции БД..." -ForegroundColor Yellow
            $message = Read-Host "Введите описание миграции"
            if ([string]::IsNullOrWhiteSpace($message)) {
                $message = "New migration"
            }
            & ".\venv\Scripts\Activate.ps1"
            alembic revision --autogenerate -m $message
        }
        "13" {
            Write-Host "⬆️ Применение миграций БД..." -ForegroundColor Yellow
            & ".\venv\Scripts\Activate.ps1"
            alembic upgrade head
        }
        "0" {
            Write-Host "👋 До свидания!" -ForegroundColor Green
            exit 0
        }
        default {
            Write-Host "❌ Неверный выбор. Попробуйте снова." -ForegroundColor Red
        }
    }
}

# Главный цикл
if ($Action -eq "menu") {
    do {
        Show-Menu
        $choice = Read-Host "Выберите действие (0-13)"
        Invoke-Action -action $choice
        
        if ($choice -ne "0") {
            Write-Host ""
            Write-Host "Нажмите любую клавишу для продолжения..." -ForegroundColor Yellow
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        }
    } while ($choice -ne "0")
} else {
    Invoke-Action -action $Action
}