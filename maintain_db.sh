#!/bin/bash

# Database maintenance script
# Run monthly or as needed to optimize database

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

DB_PATH="output/findings.db"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║        Database Maintenance - OC Monitor                  ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Timestamp: $TIMESTAMP"
echo "Database: $DB_PATH"
echo ""

if [ ! -f "$DB_PATH" ]; then
    echo "❌ Database not found: $DB_PATH"
    exit 1
fi

# Show database info before maintenance
echo "📊 Database Info (Before):"
echo "   Size: $(du -h $DB_PATH | cut -f1)"
RUN_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM monitoring_runs;" 2>/dev/null || echo "N/A")
FINDING_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM findings;" 2>/dev/null || echo "N/A")
echo "   Runs: $RUN_COUNT"
echo "   Findings: $FINDING_COUNT"
echo ""

# Check integrity first
echo "🔍 Checking database integrity..."
INTEGRITY=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1)
if [ "$INTEGRITY" = "ok" ]; then
    echo "✅ Database integrity OK"
else
    echo "❌ Database integrity issues detected:"
    echo "$INTEGRITY"
    echo ""
    echo "⚠️  Stopping maintenance - please fix integrity issues first!"
    exit 1
fi
echo ""

# Optimize database
echo "🔧 Running VACUUM (this may take a while for large databases)..."
sqlite3 "$DB_PATH" "VACUUM;" 2>&1
if [ $? -eq 0 ]; then
    echo "✅ VACUUM completed"
else
    echo "❌ VACUUM failed"
fi
echo ""

# Analyze for query optimization
echo "📊 Running ANALYZE (optimizing query planner)..."
sqlite3 "$DB_PATH" "ANALYZE;" 2>&1
if [ $? -eq 0 ]; then
    echo "✅ ANALYZE completed"
else
    echo "❌ ANALYZE failed"
fi
echo ""

# Ensure WAL mode
echo "🔄 Ensuring WAL mode is enabled..."
WAL_MODE=$(sqlite3 "$DB_PATH" "PRAGMA journal_mode=WAL;" 2>&1)
if [ "$WAL_MODE" = "wal" ]; then
    echo "✅ WAL mode enabled"
else
    echo "⚠️  WAL mode: $WAL_MODE"
fi
echo ""

# Show database info after maintenance
echo "📊 Database Info (After):"
echo "   Size: $(du -h $DB_PATH | cut -f1)"
echo "   Runs: $(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM monitoring_runs;" 2>/dev/null || echo "N/A")"
echo "   Findings: $(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM findings;" 2>/dev/null || echo "N/A")"
echo ""

# Show table statistics
echo "📋 Table Statistics:"
sqlite3 "$DB_PATH" <<'EOF'
.mode column
.headers on
SELECT 
    name as 'Table',
    CAST((SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name=m.name) AS TEXT) as 'Indexes'
FROM sqlite_master m
WHERE type='table' AND name NOT LIKE 'sqlite_%'
ORDER BY name;
EOF
echo ""

# Show recent activity
echo "🕐 Recent Activity:"
LAST_RUN=$(sqlite3 "$DB_PATH" "SELECT timestamp FROM monitoring_runs ORDER BY timestamp DESC LIMIT 1;" 2>/dev/null || echo "N/A")
echo "   Last run: $LAST_RUN"
OLDEST_RUN=$(sqlite3 "$DB_PATH" "SELECT timestamp FROM monitoring_runs ORDER BY timestamp ASC LIMIT 1;" 2>/dev/null || echo "N/A")
echo "   Oldest run: $OLDEST_RUN"
echo ""

echo "✅ Maintenance complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
