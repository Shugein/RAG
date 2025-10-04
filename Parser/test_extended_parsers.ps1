#!/usr/bin/env pwsh
# test_extended_parsers.ps1
# Тест расширенных HTML парсеров

Write-Host "🧪 Тестирование расширенных HTML парсеров" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Gray

# Проверяем виртуальное окружение
if (-not (Test-Path "venv\Scripts\activate.ps1")) {
    Write-Host "❌ Виртуальное окружение не найдено!" -ForegroundColor Red
    Write-Host "💡 Запустите setup.ps1 для создания виртуального окружения" -ForegroundColor Yellow
    exit 1
}

# Активируем виртуальное окружение
Write-Host "🔧 Активация виртуального окружения..." -ForegroundColor Yellow
& "venv\Scripts\activate.ps1"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка активации виртуального окружения" -ForegroundColor Red
    exit 1
}

# Проверяем Python
$pythonVersion = python --version 2>&1
Write-Host "🐍 Python: $pythonVersion" -ForegroundColor Green

# Запускаем тест
Write-Host "`n🚀 Запуск тестирования расширенных HTML парсеров..." -ForegroundColor Green
Write-Host "📋 Тестируемые парсеры:" -ForegroundColor Cyan
Write-Host "   - E-disclosure (новости)" -ForegroundColor White
Write-Host "   - E-disclosure (сообщения)" -ForegroundColor White
Write-Host "   - MOEX (Московская биржа)" -ForegroundColor White

python test_extended_html_parsers.py

$testResult = $LASTEXITCODE

if ($testResult -eq 0) {
    Write-Host "`n✅ Тестирование расширенных HTML парсеров завершено успешно!" -ForegroundColor Green
} else {
    Write-Host "`n❌ Тестирование завершено с ошибками (код: $testResult)" -ForegroundColor Red
}

Write-Host "`n💡 Следующие шаги:" -ForegroundColor Yellow
Write-Host "   - Проверьте логи для деталей" -ForegroundColor White
Write-Host "   - Запустите load_sources.py для обновления конфигурации" -ForegroundColor White
Write-Host "   - Используйте start_ceg_parser.ps1 для запуска полной системы" -ForegroundColor White

exit $testResult
