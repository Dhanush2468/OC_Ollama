#!/bin/bash

# Health check script for 24/7 monitoring
# Run this periodically (e.g., via cron every 5 minutes)

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

LOG_FILE="logs/health.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$TIMESTAMP] $1" >> "$LOG_FILE"
}

# Check if dashboard is responding
if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Dashboard is healthy${NC}"
    log "✅ Dashboard: HEALTHY"
else
    echo -e "${RED}❌ Dashboard is DOWN${NC}"
    log "❌ Dashboard: DOWN - Attempting restart"
    
    # Try to restart based on OS
    if command -v systemctl &> /dev/null; then
        sudo systemctl restart oc-dashboard
        log "   Restarted via systemctl"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        launchctl kickstart -k user/$(id -u)/com.oc.dashboard
        log "   Restarted via launchctl"
    fi
fi

# Check if scheduler process is running
if pgrep -f "operation_console_monitor.scheduler" > /dev/null; then
    echo -e "${GREEN}✅ Scheduler is running${NC}"
    log "✅ Scheduler: RUNNING"
else
    echo -e "${RED}❌ Scheduler is DOWN${NC}"
    log "❌ Scheduler: DOWN - Attempting restart"
    
    # Try to restart based on OS
    if command -v systemctl &> /dev/null; then
        sudo systemctl restart oc-scheduler
        log "   Restarted via systemctl"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        launchctl kickstart -k user/$(id -u)/com.oc.scheduler
        log "   Restarted via launchctl"
    fi
fi

# Check database
if [ -f "output/findings.db" ]; then
    DB_SIZE=$(du -h output/findings.db | cut -f1)
    echo -e "${GREEN}📊 Database size: $DB_SIZE${NC}"
    log "📊 Database: $DB_SIZE"
    
    # Check for large database (>500MB)
    DB_SIZE_BYTES=$(du output/findings.db | cut -f1)
    if [ "$DB_SIZE_BYTES" -gt 512000 ]; then
        echo -e "${YELLOW}⚠️  Database is large, consider cleanup${NC}"
        log "⚠️  Database size warning: $DB_SIZE"
    fi
else
    echo -e "${RED}❌ Database not found!${NC}"
    log "❌ Database: NOT FOUND"
fi

# Check log file sizes
if [ -f "logs/dashboard.log" ]; then
    DASH_LOG_SIZE=$(du -h logs/dashboard.log | cut -f1)
    echo "📝 Dashboard log: $DASH_LOG_SIZE"
    log "📝 Dashboard log: $DASH_LOG_SIZE"
fi

if [ -f "logs/scheduler.log" ]; then
    SCHED_LOG_SIZE=$(du -h logs/scheduler.log | cut -f1)
    echo "📝 Scheduler log: $SCHED_LOG_SIZE"
    log "📝 Scheduler log: $SCHED_LOG_SIZE"
fi

# Check disk space
DISK_USAGE=$(df -h "$PROJECT_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
    echo -e "${RED}❌ Disk space critical: ${DISK_USAGE}%${NC}"
    log "❌ Disk space critical: ${DISK_USAGE}%"
elif [ "$DISK_USAGE" -gt 80 ]; then
    echo -e "${YELLOW}⚠️  Disk space warning: ${DISK_USAGE}%${NC}"
    log "⚠️  Disk space warning: ${DISK_USAGE}%"
fi

echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
