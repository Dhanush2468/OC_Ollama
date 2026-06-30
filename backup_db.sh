#!/bin/bash

# Automated backup script for database
# Run daily to create backups

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

BACKUP_DIR="backups"
DB_PATH="output/findings.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_READABLE=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$BACKUP_DIR"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║          Database Backup - OC Monitor                     ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Date: $DATE_READABLE"
echo ""

if [ ! -f "$DB_PATH" ]; then
    echo "❌ Database not found: $DB_PATH"
    exit 1
fi

# Show database info
DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
echo "📊 Database size: $DB_SIZE"
echo ""

# Create backup using SQLite's backup command
echo "📦 Creating backup..."
BACKUP_FILE="$BACKUP_DIR/findings_$TIMESTAMP.db"
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Backup created: findings_$TIMESTAMP.db"
    
    # Compress backup
    echo "🗜️  Compressing backup..."
    gzip "$BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        COMPRESSED_SIZE=$(du -h "$BACKUP_FILE.gz" | cut -f1)
        echo "✅ Backup compressed: findings_$TIMESTAMP.db.gz ($COMPRESSED_SIZE)"
    else
        echo "⚠️  Compression failed, keeping uncompressed backup"
    fi
else
    echo "❌ Backup failed!"
    exit 1
fi
echo ""

# List all backups
echo "📋 Available backups:"
ls -lh "$BACKUP_DIR"/findings_*.db.gz 2>/dev/null | awk '{print "   " $9 " (" $5 ")"}'
BACKUP_COUNT=$(ls "$BACKUP_DIR"/findings_*.db.gz 2>/dev/null | wc -l)
echo "   Total: $BACKUP_COUNT backups"
echo ""

# Clean old backups (keep last 30 days)
echo "🗑️  Cleaning old backups (keeping last 30 days)..."
DELETED=$(find "$BACKUP_DIR" -name "findings_*.db.gz" -mtime +30 -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "✅ Deleted $DELETED old backup(s)"
else
    echo "✅ No old backups to delete"
fi
echo ""

# Show disk usage
BACKUP_DIR_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "💾 Backup directory size: $BACKUP_DIR_SIZE"
echo ""

echo "✅ Backup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 To restore a backup:"
echo "   gunzip backups/findings_YYYYMMDD_HHMMSS.db.gz"
echo "   cp backups/findings_YYYYMMDD_HHMMSS.db output/findings.db"
echo ""
