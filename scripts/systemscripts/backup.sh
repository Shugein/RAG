#!/bin/bash
# backup.sh

BACKUP_DIR="backups"
mkdir -p $BACKUP_DIR

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/newsdb_$TIMESTAMP.sql"

echo "Creating backup: $BACKUP_FILE"
docker-compose exec -T postgres pg_dump -U newsuser newsdb > $BACKUP_FILE

if [ $? -eq 0 ]; then
    echo "✅ Backup created successfully"
    # Compress
    gzip $BACKUP_FILE
    echo "📦 Compressed to ${BACKUP_FILE}.gz"
    
    # Keep only last 7 backups
    ls -t $BACKUP_DIR/*.gz | tail -n +8 | xargs rm -f 2>/dev/null
    echo "🗑️  Old backups cleaned"
else
    echo "❌ Backup failed"
    rm -f $BACKUP_FILE
fi