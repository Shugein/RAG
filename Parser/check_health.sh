# -------------------------------------------
# check_health.sh - Проверка здоровья системы
# -------------------------------------------

#!/bin/bash
# check_health.sh

echo "🔍 Checking system health..."
echo "=============================="

# Check PostgreSQL
echo -n "PostgreSQL: "
if docker-compose exec -T postgres pg_isready -U newsuser > /dev/null 2>&1; then
    echo "✅ Running"
    # Check tables
    TABLE_COUNT=$(docker-compose exec -T postgres psql -U newsuser -d newsdb -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')
    echo "  Tables: $TABLE_COUNT"
    NEWS_COUNT=$(docker-compose exec -T postgres psql -U newsuser -d newsdb -t -c "SELECT COUNT(*) FROM news;" 2>/dev/null | tr -d ' ' || echo "0")
    echo "  News items: $NEWS_COUNT"
else
    echo "❌ Not running"
fi

# Check RabbitMQ
echo -n "RabbitMQ: "
if curl -s -u admin:admin123 http://localhost:15672/api/overview > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not running"
fi

# Check Redis
echo -n "Redis: "
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not running"
fi

# Check API
echo -n "API: "
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Running"
    SOURCES=$(curl -s http://localhost:8000/sources | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "  Sources: $SOURCES"
else
    echo "❌ Not running"
fi

echo ""
echo "📊 URLs:"
echo "  API Docs: http://localhost:8000/docs"
echo "  RabbitMQ: http://localhost:15672 (admin/admin123)"
echo "  Metrics:  http://localhost:9090"
