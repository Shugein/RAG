# view_logs.ps1 - Скрипт для просмотра логов
# Запустите: .\view_logs.ps1

param(
    [string]$Service = "all",
    [int]$Lines = 50
)

Write-Host "Viewing logs for: $Service" -ForegroundColor Green
Write-Host "Lines: $Lines" -ForegroundColor Yellow
Write-Host ""

switch ($Service.ToLower()) {
    "api" {
        Write-Host "=== API Server Logs ===" -ForegroundColor Cyan
        docker logs --tail $Lines news-api
    }
    "telegram" {
        Write-Host "=== Telegram_Parser Logs ===" -ForegroundColor Cyan
        docker logs --tail $Lines news-telegram-parser
    }
    "outbox" {
        Write-Host "=== Outbox Relay Logs ===" -ForegroundColor Cyan
        docker logs --tail $Lines news-outbox-relay
    }
    "enricher" {
        Write-Host "=== Enricher Logs ===" -ForegroundColor Cyan
        docker logs --tail $Lines news-enricher
    }
    "postgres" {
        Write-Host "=== PostgreSQL Logs ===" -ForegroundColor Cyan
        docker logs --tail $Lines news-postgres
    }
    "rabbitmq" {
        Write-Host "=== RabbitMQ Logs ===" -ForegroundColor Cyan
        docker logs --tail $Lines news-rabbitmq
    }
    "redis" {
        Write-Host "=== Redis Logs ===" -ForegroundColor Cyan
        docker logs --tail $Lines news-redis
    }
    "all" {
        Write-Host "=== All Services Logs ===" -ForegroundColor Cyan
        docker-compose logs --tail $Lines
    }
    default {
        Write-Host "Available services: api, telegram, outbox, enricher, postgres, rabbitmq, redis, all" -ForegroundColor Red
        Write-Host "Usage: .\view_logs.ps1 -Service <service_name> -Lines <number>" -ForegroundColor Yellow
    }
}
