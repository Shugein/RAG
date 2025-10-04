# Руководство по работе с дампами Neo4j

Это руководство описывает, как создавать и восстанавливать дампы базы данных Neo4j в проекте.

## 📋 Содержание

- [Создание дампа](#создание-дампа)
- [Восстановление дампа](#восстановление-дампа)
- [Форматы дампов](#форматы-дампов)
- [Примеры использования](#примеры-использования)
- [Устранение неполадок](#устранение-неполадок)

## 🚀 Создание дампа

### Быстрый способ (PowerShell)

```powershell
# Создать дамп во всех форматах
.\export_neo4j_dump.ps1

# Создать только Cypher дамп
.\export_neo4j_dump.ps1 -Format cypher

# Указать директорию для сохранения
.\export_neo4j_dump.ps1 -OutputDir C:\backups
```

### Ручной способ (Python)

```bash
# Активировать виртуальное окружение
venv\Scripts\activate

# Запустить скрипт экспорта
python scripts\export_neo4j_dump.py
```

### Через Docker (cypher-shell)

```bash
# Экспорт через cypher-shell
docker exec -it radar-neo4j cypher-shell -u neo4j -p password123 -d neo4j "MATCH (n) RETURN n" > dump.cypher

# Или полный дамп
docker exec -it radar-neo4j cypher-shell -u neo4j -p password123 -d neo4j "CALL apoc.export.cypher.all('dump.cypher', {})"
```

## 📥 Восстановление дампа

### Быстрый способ (PowerShell)

```powershell
# Восстановить из Cypher файла
.\import_neo4j_dump.ps1 -DumpFile dumps\neo4j_dump_20241203_143022.cypher

# Восстановить с очисткой базы данных
.\import_neo4j_dump.ps1 -DumpFile dumps\neo4j_dump_20241203_143022.cypher -Clear

# Восстановить с проверкой
.\import_neo4j_dump.ps1 -DumpFile dumps\neo4j_dump_20241203_143022.cypher -Verify
```

### Ручной способ (Python)

```bash
# Активировать виртуальное окружение
venv\Scripts\activate

# Восстановить из Cypher файла
python scripts\import_neo4j_dump.py dumps\neo4j_dump_20241203_143022.cypher

# Восстановить с очисткой
python scripts\import_neo4j_dump.py dumps\neo4j_dump_20241203_143022.cypher --clear

# Восстановить с проверкой
python scripts\import_neo4j_dump.py dumps\neo4j_dump_20241203_143022.cypher --verify
```

### Через Docker (cypher-shell)

```bash
# Восстановление из Cypher файла
docker exec -i radar-neo4j cypher-shell -u neo4j -p password123 -d neo4j < dumps\neo4j_dump_20241203_143022.cypher

# Или через файл
docker cp dumps\neo4j_dump_20241203_143022.cypher radar-neo4j:/tmp/dump.cypher
docker exec -it radar-neo4j cypher-shell -u neo4j -p password123 -d neo4j -f /tmp/dump.cypher
```

## 📁 Форматы дампов

### 1. Cypher (.cypher)
- **Описание**: Скрипт с командами CREATE/MERGE
- **Преимущества**: Легко читается, можно редактировать
- **Недостатки**: Может быть большим для больших баз данных
- **Использование**: Ручное восстановление, миграции

### 2. JSON (.json)
- **Описание**: Структурированные данные в JSON формате
- **Преимущества**: Легко обрабатывается программами
- **Недостатки**: Больший размер файла
- **Использование**: Программная обработка, интеграции

### 3. CSV (директория)
- **Описание**: Отдельные файлы для узлов и связей
- **Преимущества**: Легко импортировать в другие системы
- **Недостатки**: Теряется информация о типах данных
- **Использование**: Анализ данных, экспорт в другие БД

## 💡 Примеры использования

### Создание резервной копии перед изменениями

```powershell
# 1. Создать дамп
.\export_neo4j_dump.ps1 -OutputDir backups\before_changes

# 2. Внести изменения в базу данных
# ... ваши изменения ...

# 3. При необходимости восстановить
.\import_neo4j_dump.ps1 -DumpFile backups\before_changes\neo4j_dump_*.cypher -Clear
```

### Миграция данных между окружениями

```powershell
# На продакшене
.\export_neo4j_dump.ps1 -OutputDir migration\prod_dump

# На тестовом окружении
.\import_neo4j_dump.ps1 -DumpFile migration\prod_dump\neo4j_dump_*.cypher -Clear -Verify
```

### Анализ данных

```powershell
# Создать CSV дамп для анализа
.\export_neo4j_dump.ps1 -Format csv -OutputDir analysis

# Открыть файлы в Excel или другой программе
# analysis\neo4j_dump_*\nodes_*.csv
# analysis\neo4j_dump_*\relationships_*.csv
```

## 🔧 Устранение неполадок

### Neo4j не запущен

```powershell
# Запустить Neo4j
docker-compose up -d neo4j

# Проверить статус
docker ps --filter "name=radar-neo4j"
```

### Ошибки подключения

```powershell
# Проверить настройки подключения
Get-Content .env | Select-String "NEO4J"

# Проверить доступность портов
netstat -an | Select-String "7474|7687"
```

### Ошибки импорта

```powershell
# Проверить логи Neo4j
docker logs radar-neo4j

# Очистить базу данных вручную
docker exec -it radar-neo4j cypher-shell -u neo4j -p password123 -d neo4j "MATCH (n) DETACH DELETE n"
```

### Большие дампы

```powershell
# Для больших баз данных используйте cypher-shell напрямую
docker exec -it radar-neo4j cypher-shell -u neo4j -p password123 -d neo4j "CALL apoc.export.cypher.all('large_dump.cypher', {})"

# Или экспортируйте по частям
python scripts\export_neo4j_dump.py  # Только узлы определенного типа
```

## 📊 Мониторинг и проверка

### Проверка состояния базы данных

```cypher
// В Neo4j Browser (http://localhost:7474)
// Статистика узлов
MATCH (n) RETURN labels(n) as node_type, count(n) as count ORDER BY count DESC

// Статистика связей
MATCH ()-[r]->() RETURN type(r) as relationship_type, count(r) as count ORDER BY count DESC

// Размер базы данных
CALL db.stats.retrieve('GRAPH COUNTS')
```

### Проверка целостности данных

```cypher
// Проверка связей без узлов
MATCH (a)-[r]->(b) WHERE a IS NULL OR b IS NULL RETURN count(r)

// Проверка дубликатов
MATCH (n) WITH n, count(n) as cnt WHERE cnt > 1 RETURN labels(n), cnt
```

## 🚨 Важные замечания

1. **Всегда создавайте резервные копии** перед важными изменениями
2. **Тестируйте восстановление** на тестовом окружении
3. **Проверяйте размер дампов** - большие файлы могут вызвать проблемы
4. **Используйте очистку базы данных** только при необходимости
5. **Сохраняйте дампы в безопасном месте** с регулярным резервным копированием

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker logs radar-neo4j`
2. Убедитесь, что Neo4j запущен: `docker ps`
3. Проверьте подключение: `http://localhost:7474`
4. Обратитесь к документации Neo4j: https://neo4j.com/docs/
