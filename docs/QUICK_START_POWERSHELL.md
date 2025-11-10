# 🚀 Быстрый старт - PowerShell

## Установка и запуск за 3 шага

### 1️⃣ Установка
```powershell
.\setup.ps1
```

### 2️⃣ Настройка Telegram
```powershell
.\setup_telegram.ps1
```

### 3️⃣ Запуск
```powershell
.\start_dev.ps1
```

## ✅ Готово!

Откройте браузер:
- **API**: http://localhost:8000/docs
- **RabbitMQ**: http://localhost:15672 (admin/admin123)
- **Neo4j Browser**: http://localhost:7474 (neo4j/password123)

## 🛑 Остановка
```powershell
.\stop_dev.ps1
```

## 🔧 Полезные команды

| Команда | Описание |
|---------|----------|
| `.\check_health.ps1` | Проверка здоровья системы |
| `.\view_logs.ps1` | Просмотр логов |
| `.\reset_project.ps1` | Полный сброс проекта |

## ❓ Проблемы?

1. **PowerShell не выполняет скрипты:**
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

2. **Docker не запускается:**
   - Запустите Docker Desktop
   - Проверьте WSL2

3. **Порты заняты:**
   ```powershell
   netstat -ano | findstr :8000
   taskkill /PID <PID> /F
   ```

---
📖 **Полная документация**: [README_POWERSHELL.md](README_POWERSHELL.md)
