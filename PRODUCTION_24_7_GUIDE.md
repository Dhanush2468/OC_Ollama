# 24/7 Production Deployment Guide

**Operation Console Monitor Dashboard - Always-On Local Deployment**

---

## Overview

This guide covers running the dashboard **24/7 on a local machine** alongside the scheduled monitoring orchestrator. Both services will auto-restart on failure and survive system reboots.

---

## Architecture for 24/7 Operation

```
┌─────────────────────────────────────────────────────┐
│              Local Machine (24/7)                    │
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │  Dashboard Service (Port 8080)             │    │
│  │  • Auto-restart on failure                 │    │
│  │  • Survives reboots                        │    │
│  │  • Logs to file                            │    │
│  └────────────────┬───────────────────────────┘    │
│                   │ (reads)                         │
│                   ▼                                 │
│  ┌────────────────────────────────────────────┐    │
│  │  SQLite Database (output/findings.db)      │    │
│  │  • WAL mode (concurrent access)            │    │
│  └────────────────▲───────────────────────────┘    │
│                   │ (writes)                        │
│                   │                                 │
│  ┌────────────────┴───────────────────────────┐    │
│  │  Monitoring Scheduler                      │    │
│  │  • Runs at scheduled intervals             │    │
│  │  • Auto-restart on failure                 │    │
│  │  • Survives reboots                        │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## Quick Start (3 Steps)

```bash
# 1. Install as services
sudo ./install_services.sh

# 2. Start services
sudo systemctl start oc-dashboard
sudo systemctl start oc-scheduler

# 3. Enable auto-start on boot
sudo systemctl enable oc-dashboard
sudo systemctl enable oc-scheduler
```

**Dashboard URL:** http://localhost:8080

---

## Option 1: systemd Services (Linux - Recommended)

### Step 1: Create Dashboard Service File

Create `/etc/systemd/system/oc-dashboard.service`:

```ini
[Unit]
Description=Operation Console Monitor Dashboard
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=your_username
Group=your_username
WorkingDirectory=/Users/Dhanush.V/Desktop/oc/agent
Environment="PATH=/usr/local/bin:/usr/bin:/bin"

# Main command
ExecStart=/usr/bin/python3 run_dashboard.py --host 0.0.0.0 --port 8080

# Restart configuration
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# Logging
StandardOutput=append:/Users/Dhanush.V/Desktop/oc/agent/logs/dashboard.log
StandardError=append:/Users/Dhanush.V/Desktop/oc/agent/logs/dashboard-error.log

# Resource limits
MemoryLimit=512M
CPUQuota=50%

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Step 2: Create Scheduler Service File

Create `/etc/systemd/system/oc-scheduler.service`:

```ini
[Unit]
Description=Operation Console Monitor Scheduler
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=your_username
Group=your_username
WorkingDirectory=/Users/Dhanush.V/Desktop/oc/agent
Environment="PATH=/usr/local/bin:/usr/bin:/bin"

# Main command
ExecStart=/usr/bin/python3 -m operation_console_monitor.scheduler --config config/monitor.yaml

# Restart configuration
Restart=always
RestartSec=30
StartLimitInterval=300
StartLimitBurst=5

# Logging
StandardOutput=append:/Users/Dhanush.V/Desktop/oc/agent/logs/scheduler.log
StandardError=append:/Users/Dhanush.V/Desktop/oc/agent/logs/scheduler-error.log

# Resource limits
MemoryLimit=1G
CPUQuota=75%

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Step 3: Install and Start Services

```bash
# Create logs directory
mkdir -p /Users/Dhanush.V/Desktop/oc/agent/logs

# Set correct permissions
sudo chown your_username:your_username /etc/systemd/system/oc-*.service
chmod 644 /etc/systemd/system/oc-*.service

# Reload systemd
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable oc-dashboard
sudo systemctl enable oc-scheduler

# Start services now
sudo systemctl start oc-dashboard
sudo systemctl start oc-scheduler

# Check status
sudo systemctl status oc-dashboard
sudo systemctl status oc-scheduler
```

### Step 4: Verify Running

```bash
# Check if dashboard is responding
curl http://localhost:8080/health

# Check logs
tail -f logs/dashboard.log
tail -f logs/scheduler.log

# Check system status
sudo systemctl status oc-dashboard
sudo systemctl status oc-scheduler
```

---

## Option 2: macOS LaunchAgent (for macOS)

### Step 1: Create Dashboard LaunchAgent

Create `~/Library/LaunchAgents/com.oc.dashboard.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.oc.dashboard</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>run_dashboard.py</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8080</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>/Users/Dhanush.V/Desktop/oc/agent</string>
    
    <key>StandardOutPath</key>
    <string>/Users/Dhanush.V/Desktop/oc/agent/logs/dashboard.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/Dhanush.V/Desktop/oc/agent/logs/dashboard-error.log</string>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <key>ProcessType</key>
    <string>Background</string>
    
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
```

### Step 2: Create Scheduler LaunchAgent

Create `~/Library/LaunchAgents/com.oc.scheduler.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.oc.scheduler</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>-m</string>
        <string>operation_console_monitor.scheduler</string>
        <string>--config</string>
        <string>config/monitor.yaml</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>/Users/Dhanush.V/Desktop/oc/agent</string>
    
    <key>StandardOutPath</key>
    <string>/Users/Dhanush.V/Desktop/oc/agent/logs/scheduler.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/Dhanush.V/Desktop/oc/agent/logs/scheduler-error.log</string>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <key>ProcessType</key>
    <string>Background</string>
    
    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
```

### Step 3: Install and Start LaunchAgents

```bash
# Create logs directory
mkdir -p /Users/Dhanush.V/Desktop/oc/agent/logs

# Load LaunchAgents
launchctl load ~/Library/LaunchAgents/com.oc.dashboard.plist
launchctl load ~/Library/LaunchAgents/com.oc.scheduler.plist

# Check status
launchctl list | grep com.oc

# View logs
tail -f logs/dashboard.log
tail -f logs/scheduler.log
```

### Unload Services (if needed)

```bash
launchctl unload ~/Library/LaunchAgents/com.oc.dashboard.plist
launchctl unload ~/Library/LaunchAgents/com.oc.scheduler.plist
```

---

## Option 3: Docker Compose (Cross-Platform)

### docker-compose.yml

```yaml
version: '3.8'

services:
  dashboard:
    build: .
    container_name: oc-dashboard
    ports:
      - "8080:8080"
    volumes:
      - ./config:/app/config:ro
      - ./output:/app/output
      - ./logs:/app/logs
    environment:
      - PYTHONUNBUFFERED=1
    command: python run_dashboard.py --host 0.0.0.0 --port 8080
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  scheduler:
    build: .
    container_name: oc-scheduler
    volumes:
      - ./config:/app/config:ro
      - ./output:/app/output
      - ./logs:/app/logs
    environment:
      - PYTHONUNBUFFERED=1
    command: python -m operation_console_monitor.scheduler --config config/monitor.yaml
    restart: always
    depends_on:
      - dashboard
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p logs output

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8080/health')"

EXPOSE 8080

CMD ["python", "run_dashboard.py", "--host", "0.0.0.0", "--port", "8080"]
```

### Run with Docker Compose

```bash
# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f dashboard
docker-compose logs -f scheduler

# Stop services
docker-compose down

# Restart services
docker-compose restart
```

---

## Monitoring & Maintenance

### 1. Health Checks

**Automated Health Check Script** (`check_health.sh`):

```bash
#!/bin/bash

# Check if dashboard is responding
if curl -f -s http://localhost:8080/health > /dev/null; then
    echo "✅ Dashboard is healthy"
else
    echo "❌ Dashboard is DOWN - restarting..."
    sudo systemctl restart oc-dashboard
fi

# Check if scheduler process is running
if pgrep -f "operation_console_monitor.scheduler" > /dev/null; then
    echo "✅ Scheduler is running"
else
    echo "❌ Scheduler is DOWN - restarting..."
    sudo systemctl restart oc-scheduler
fi

# Check database size
DB_SIZE=$(du -h output/findings.db | cut -f1)
echo "📊 Database size: $DB_SIZE"

# Check log file sizes
DASH_LOG_SIZE=$(du -h logs/dashboard.log | cut -f1)
SCHED_LOG_SIZE=$(du -h logs/scheduler.log | cut -f1)
echo "📝 Dashboard log: $DASH_LOG_SIZE"
echo "📝 Scheduler log: $SCHED_LOG_SIZE"
```

**Schedule health checks with cron:**

```bash
# Edit crontab
crontab -e

# Add health check every 5 minutes
*/5 * * * * /Users/Dhanush.V/Desktop/oc/agent/check_health.sh >> /Users/Dhanush.V/Desktop/oc/agent/logs/health.log 2>&1
```

### 2. Log Rotation

**Create `/etc/logrotate.d/oc-monitor`:**

```
/Users/Dhanush.V/Desktop/oc/agent/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 your_username your_username
    postrotate
        systemctl reload oc-dashboard > /dev/null 2>&1 || true
        systemctl reload oc-scheduler > /dev/null 2>&1 || true
    endscript
}
```

### 3. Database Maintenance

**Create database maintenance script** (`maintain_db.sh`):

```bash
#!/bin/bash

DB_PATH="/Users/Dhanush.V/Desktop/oc/agent/output/findings.db"

echo "🔧 Running database maintenance..."

# Optimize database
sqlite3 "$DB_PATH" "VACUUM;"
echo "✅ VACUUM completed"

# Analyze for query optimization
sqlite3 "$DB_PATH" "ANALYZE;"
echo "✅ ANALYZE completed"

# Check integrity
INTEGRITY=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;")
if [ "$INTEGRITY" = "ok" ]; then
    echo "✅ Database integrity OK"
else
    echo "❌ Database integrity issues: $INTEGRITY"
fi

# Show database stats
echo "📊 Database size: $(du -h $DB_PATH | cut -f1)"
echo "📊 Run count: $(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM monitoring_runs;")"
echo "📊 Findings count: $(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM findings;")"
```

**Schedule monthly maintenance:**

```bash
# Run on first day of month at 2am
0 2 1 * * /Users/Dhanush.V/Desktop/oc/agent/maintain_db.sh >> /Users/Dhanush.V/Desktop/oc/agent/logs/maintenance.log 2>&1
```

### 4. Backup Strategy

**Automated backup script** (`backup_db.sh`):

```bash
#!/bin/bash

BACKUP_DIR="/Users/Dhanush.V/Desktop/oc/agent/backups"
DB_PATH="/Users/Dhanush.V/Desktop/oc/agent/output/findings.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Create backup
echo "📦 Creating backup..."
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/findings_$TIMESTAMP.db'"

# Compress backup
gzip "$BACKUP_DIR/findings_$TIMESTAMP.db"
echo "✅ Backup created: findings_$TIMESTAMP.db.gz"

# Keep only last 30 days
find "$BACKUP_DIR" -name "findings_*.db.gz" -mtime +30 -delete
echo "🗑️  Cleaned old backups (>30 days)"
```

**Schedule daily backups:**

```bash
# Daily backup at 3am
0 3 * * * /Users/Dhanush.V/Desktop/oc/agent/backup_db.sh >> /Users/Dhanush.V/Desktop/oc/agent/logs/backup.log 2>&1
```

---

## Performance Optimization for 24/7

### 1. Resource Limits

**Adjust systemd service limits** (edit `/etc/systemd/system/oc-dashboard.service`):

```ini
# Recommended for 24/7 operation
MemoryLimit=512M
MemoryHigh=400M
CPUQuota=50%
TasksMax=100
```

### 2. Database Optimization

**In `config/monitor.yaml`**, optimize database settings:

```yaml
dashboard:
  database_path: "./output/findings.db"
  connection_pool_size: 5
  connection_timeout: 30
  enable_wal: true  # WAL mode for concurrent access
  cache_size: -64000  # 64MB cache
  
  # Cleanup old data (optional)
  auto_cleanup:
    enabled: true
    keep_days: 90  # Keep 90 days of data
    run_interval: "0 4 * * *"  # 4am daily
```

### 3. Memory Management

**Add to `run_dashboard.py`:**

```python
import gc

# Enable garbage collection optimization
gc.set_threshold(700, 10, 10)

# Run periodic cleanup (add to FastAPI startup)
@app.on_event("startup")
async def startup_gc():
    asyncio.create_task(periodic_gc())

async def periodic_gc():
    while True:
        await asyncio.sleep(3600)  # Every hour
        gc.collect()
```

---

## Troubleshooting 24/7 Operation

### Common Issues

**1. Dashboard not starting after reboot**

```bash
# Check service status
sudo systemctl status oc-dashboard

# Check logs
journalctl -u oc-dashboard -n 50

# Common causes:
# - Database locked (wait or restart both services)
# - Port already in use
# - Permission issues
```

**2. High memory usage**

```bash
# Check memory usage
ps aux | grep python

# Restart services to free memory
sudo systemctl restart oc-dashboard
sudo systemctl restart oc-scheduler
```

**3. Database locked errors**

```bash
# Check what's accessing the database
lsof output/findings.db

# Ensure WAL mode is enabled
sqlite3 output/findings.db "PRAGMA journal_mode=WAL;"
```

**4. Logs growing too large**

```bash
# Check log sizes
du -h logs/

# Manual log rotation
logrotate -f /etc/logrotate.d/oc-monitor

# Or truncate logs
> logs/dashboard.log
> logs/scheduler.log
```

---

## Monitoring Dashboard (Optional)

### Simple Monitoring Page

Create `monitor_status.sh` for quick status check:

```bash
#!/bin/bash

clear
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     Operation Console Monitor - 24/7 Status               ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Dashboard status
if systemctl is-active --quiet oc-dashboard; then
    echo "✅ Dashboard:  RUNNING"
    UPTIME=$(systemctl show oc-dashboard -p ActiveEnterTimestamp --value)
    echo "   Uptime: $UPTIME"
else
    echo "❌ Dashboard:  STOPPED"
fi

# Scheduler status
if systemctl is-active --quiet oc-scheduler; then
    echo "✅ Scheduler:  RUNNING"
    UPTIME=$(systemctl show oc-scheduler -p ActiveEnterTimestamp --value)
    echo "   Uptime: $UPTIME"
else
    echo "❌ Scheduler:  STOPPED"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Resource usage
echo "💻 Resource Usage:"
echo "   $(free -h | grep Mem | awk '{print "Memory: " $3 "/" $2}')"
echo "   $(df -h /Users/Dhanush.V/Desktop/oc/agent | tail -1 | awk '{print "Disk: " $3 "/" $2 " (" $5 " used)"}')"

echo ""

# Database stats
DB_SIZE=$(du -h output/findings.db | cut -f1)
RUN_COUNT=$(sqlite3 output/findings.db "SELECT COUNT(*) FROM monitoring_runs;")
echo "📊 Database:"
echo "   Size: $DB_SIZE"
echo "   Runs: $RUN_COUNT"

echo ""

# Recent activity
LAST_RUN=$(sqlite3 output/findings.db "SELECT timestamp FROM monitoring_runs ORDER BY timestamp DESC LIMIT 1;")
echo "🕐 Last Run: $LAST_RUN"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Dashboard URL: http://localhost:8080"
echo ""
```

Run anytime to check status:
```bash
./monitor_status.sh
```

---

## Production Checklist

Before going live with 24/7 operation:

- [ ] Services installed and enabled (auto-start on boot)
- [ ] Log rotation configured
- [ ] Database backup scheduled
- [ ] Health checks automated
- [ ] Database maintenance scheduled
- [ ] Monitoring dashboard accessible
- [ ] Resource limits configured
- [ ] WAL mode enabled on database
- [ ] Tested service restart on failure
- [ ] Tested system reboot (services auto-start)
- [ ] Documentation reviewed
- [ ] Access credentials documented (if auth added later)

---

## Quick Reference

### Service Management

```bash
# Start services
sudo systemctl start oc-dashboard oc-scheduler

# Stop services
sudo systemctl stop oc-dashboard oc-scheduler

# Restart services
sudo systemctl restart oc-dashboard oc-scheduler

# Check status
sudo systemctl status oc-dashboard oc-scheduler

# View logs (live)
journalctl -u oc-dashboard -f
journalctl -u oc-scheduler -f

# View recent logs
journalctl -u oc-dashboard -n 100
journalctl -u oc-scheduler -n 100
```

### Emergency Commands

```bash
# Kill all related processes
pkill -f "run_dashboard"
pkill -f "operation_console_monitor.scheduler"

# Clear database locks
rm output/findings.db-shm output/findings.db-wal

# Reset services
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

---

## Support & Maintenance

For 24/7 operation support:
1. Check logs first: `logs/dashboard.log` and `logs/scheduler.log`
2. Verify health: `curl http://localhost:8080/health`
3. Check service status: `sudo systemctl status oc-dashboard oc-scheduler`
4. Review system resources: `htop` or `top`

**Maintenance Windows:**
- Database optimization: Monthly (1st day, 2am)
- Log rotation: Daily (automatic)
- Backups: Daily (3am)
- Health checks: Every 5 minutes

---

**Deployment Date:** 2026-06-30  
**Last Updated:** 2026-06-30  
**Recommended Review:** Quarterly
