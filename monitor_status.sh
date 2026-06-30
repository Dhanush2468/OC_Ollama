#!/bin/bash

# Status monitoring script for 24/7 operation
# Shows real-time status of all services and resources

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

clear

echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     Operation Console Monitor - 24/7 Status              ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Timestamp: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo ""

# Detect OS for service management
if command -v systemctl &> /dev/null; then
    SERVICE_TYPE="systemd"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    SERVICE_TYPE="launchctl"
else
    SERVICE_TYPE="unknown"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}📊 SERVICE STATUS${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Dashboard status
if [ "$SERVICE_TYPE" = "systemd" ]; then
    if systemctl is-active --quiet oc-dashboard 2>/dev/null; then
        echo -e "${GREEN}✅ Dashboard:  RUNNING${NC}"
        UPTIME=$(systemctl show oc-dashboard -p ActiveEnterTimestamp --value 2>/dev/null)
        echo -e "   Uptime: $UPTIME"
        MEM_USAGE=$(systemctl show oc-dashboard -p MemoryCurrent --value 2>/dev/null)
        if [ -n "$MEM_USAGE" ] && [ "$MEM_USAGE" != "18446744073709551615" ]; then
            MEM_MB=$((MEM_USAGE / 1024 / 1024))
            echo -e "   Memory: ${MEM_MB}MB"
        fi
    else
        echo -e "${RED}❌ Dashboard:  STOPPED${NC}"
    fi
    echo ""
    
    if systemctl is-active --quiet oc-scheduler 2>/dev/null; then
        echo -e "${GREEN}✅ Scheduler:  RUNNING${NC}"
        UPTIME=$(systemctl show oc-scheduler -p ActiveEnterTimestamp --value 2>/dev/null)
        echo -e "   Uptime: $UPTIME"
        MEM_USAGE=$(systemctl show oc-scheduler -p MemoryCurrent --value 2>/dev/null)
        if [ -n "$MEM_USAGE" ] && [ "$MEM_USAGE" != "18446744073709551615" ]; then
            MEM_MB=$((MEM_USAGE / 1024 / 1024))
            echo -e "   Memory: ${MEM_MB}MB"
        fi
    else
        echo -e "${RED}❌ Scheduler:  STOPPED${NC}"
    fi
    
elif [ "$SERVICE_TYPE" = "launchctl" ]; then
    DASH_STATUS=$(launchctl list | grep com.oc.dashboard)
    if [ -n "$DASH_STATUS" ]; then
        PID=$(echo "$DASH_STATUS" | awk '{print $1}')
        if [ "$PID" != "-" ]; then
            echo -e "${GREEN}✅ Dashboard:  RUNNING (PID: $PID)${NC}"
            # Get process info
            if ps -p "$PID" > /dev/null 2>&1; then
                MEM=$(ps -p "$PID" -o rss= | awk '{printf "%.1fMB", $1/1024}')
                CPU=$(ps -p "$PID" -o %cpu= | awk '{print $1"%"}')
                echo -e "   Memory: $MEM"
                echo -e "   CPU: $CPU"
            fi
        else
            echo -e "${RED}❌ Dashboard:  STOPPED${NC}"
        fi
    else
        echo -e "${RED}❌ Dashboard:  NOT INSTALLED${NC}"
    fi
    echo ""
    
    SCHED_STATUS=$(launchctl list | grep com.oc.scheduler)
    if [ -n "$SCHED_STATUS" ]; then
        PID=$(echo "$SCHED_STATUS" | awk '{print $1}')
        if [ "$PID" != "-" ]; then
            echo -e "${GREEN}✅ Scheduler:  RUNNING (PID: $PID)${NC}"
            if ps -p "$PID" > /dev/null 2>&1; then
                MEM=$(ps -p "$PID" -o rss= | awk '{printf "%.1fMB", $1/1024}')
                CPU=$(ps -p "$PID" -o %cpu= | awk '{print $1"%"}')
                echo -e "   Memory: $MEM"
                echo -e "   CPU: $CPU"
            fi
        else
            echo -e "${RED}❌ Scheduler:  STOPPED${NC}"
        fi
    else
        echo -e "${RED}❌ Scheduler:  NOT INSTALLED${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Unknown service manager${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}🌐 NETWORK STATUS${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test dashboard endpoint
if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Dashboard responding on http://localhost:8080${NC}"
    
    # Get response time
    RESPONSE_TIME=$(curl -o /dev/null -s -w '%{time_total}' http://localhost:8080/health)
    echo -e "   Response time: ${RESPONSE_TIME}s"
else
    echo -e "${RED}❌ Dashboard not responding${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}💻 SYSTEM RESOURCES${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Memory info
if command -v free &> /dev/null; then
    MEM_INFO=$(free -h | grep Mem)
    MEM_USED=$(echo "$MEM_INFO" | awk '{print $3}')
    MEM_TOTAL=$(echo "$MEM_INFO" | awk '{print $2}')
    MEM_PERCENT=$(echo "$MEM_INFO" | awk '{printf "%.1f", ($3/$2)*100}')
    echo -e "Memory: $MEM_USED / $MEM_TOTAL (${MEM_PERCENT}%)"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    VM_STAT=$(vm_stat)
    PAGE_SIZE=4096
    FREE_PAGES=$(echo "$VM_STAT" | grep "Pages free" | awk '{print $3}' | sed 's/\.//')
    ACTIVE_PAGES=$(echo "$VM_STAT" | grep "Pages active" | awk '{print $3}' | sed 's/\.//')
    FREE_MB=$((FREE_PAGES * PAGE_SIZE / 1024 / 1024))
    ACTIVE_MB=$((ACTIVE_PAGES * PAGE_SIZE / 1024 / 1024))
    echo -e "Memory: ${ACTIVE_MB}MB active, ${FREE_MB}MB free"
fi

# Disk info
DISK_INFO=$(df -h "$PROJECT_DIR" | tail -1)
DISK_USED=$(echo "$DISK_INFO" | awk '{print $3}')
DISK_TOTAL=$(echo "$DISK_INFO" | awk '{print $2}')
DISK_PERCENT=$(echo "$DISK_INFO" | awk '{print $5}' | sed 's/%//')
echo -e "Disk:   $DISK_USED / $DISK_TOTAL (${DISK_PERCENT}%)"

if [ "$DISK_PERCENT" -gt 90 ]; then
    echo -e "${RED}   ⚠️  WARNING: Disk usage critical!${NC}"
elif [ "$DISK_PERCENT" -gt 80 ]; then
    echo -e "${YELLOW}   ⚠️  WARNING: Disk usage high${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}📊 DATABASE STATUS${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "output/findings.db" ]; then
    DB_SIZE=$(du -h output/findings.db | cut -f1)
    echo -e "${GREEN}✅ Database found${NC}"
    echo -e "   Size: $DB_SIZE"
    
    RUN_COUNT=$(sqlite3 output/findings.db "SELECT COUNT(*) FROM monitoring_runs;" 2>/dev/null || echo "N/A")
    FINDING_COUNT=$(sqlite3 output/findings.db "SELECT COUNT(*) FROM findings;" 2>/dev/null || echo "N/A")
    WORKFLOW_COUNT=$(sqlite3 output/findings.db "SELECT COUNT(*) FROM workflow_results;" 2>/dev/null || echo "N/A")
    
    echo -e "   Runs: $RUN_COUNT"
    echo -e "   Findings: $FINDING_COUNT"
    echo -e "   Workflow Results: $WORKFLOW_COUNT"
    
    # Last run
    LAST_RUN=$(sqlite3 output/findings.db "SELECT timestamp FROM monitoring_runs ORDER BY timestamp DESC LIMIT 1;" 2>/dev/null || echo "N/A")
    echo -e "   Last run: $LAST_RUN"
else
    echo -e "${RED}❌ Database not found${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}📝 LOG FILES${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "logs/dashboard.log" ]; then
    DASH_LOG_SIZE=$(du -h logs/dashboard.log | cut -f1)
    DASH_LOG_LINES=$(wc -l < logs/dashboard.log)
    echo -e "Dashboard log:  $DASH_LOG_SIZE ($DASH_LOG_LINES lines)"
else
    echo -e "Dashboard log:  ${YELLOW}Not found${NC}"
fi

if [ -f "logs/scheduler.log" ]; then
    SCHED_LOG_SIZE=$(du -h logs/scheduler.log | cut -f1)
    SCHED_LOG_LINES=$(wc -l < logs/scheduler.log)
    echo -e "Scheduler log:  $SCHED_LOG_SIZE ($SCHED_LOG_LINES lines)"
else
    echo -e "Scheduler log:  ${YELLOW}Not found${NC}"
fi

if [ -f "logs/dashboard-error.log" ]; then
    ERROR_LINES=$(wc -l < logs/dashboard-error.log)
    if [ "$ERROR_LINES" -gt 0 ]; then
        echo -e "${YELLOW}Dashboard errors: $ERROR_LINES lines${NC}"
    fi
fi

if [ -f "logs/scheduler-error.log" ]; then
    ERROR_LINES=$(wc -l < logs/scheduler-error.log)
    if [ "$ERROR_LINES" -gt 0 ]; then
        echo -e "${YELLOW}Scheduler errors: $ERROR_LINES lines${NC}"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}🔗 QUICK LINKS${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "Dashboard:      ${BLUE}http://localhost:8080${NC}"
echo -e "API Docs:       ${BLUE}http://localhost:8080/api/docs${NC}"
echo -e "Health Check:   ${BLUE}http://localhost:8080/health${NC}"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
