# Running the Operation Console Monitor Dashboard

**Version:** 1.0.0  
**Date:** 2026-06-30  
**Status:** Ready for Testing

---

## Quick Start

### 1. Start the Dashboard

```bash
cd /path/to/agent
python run_dashboard.py
```

### 2. Open in Browser

Visit: **http://localhost:8080**

### 3. Explore

- Home Dashboard: http://localhost:8080
- API Documentation: http://localhost:8080/api/docs
- Alternative API Docs: http://localhost:8080/api/redoc

---

## Prerequisites

### System Requirements

- **Python:** 3.11 or higher
- **Operating System:** macOS, Linux, or Windows
- **RAM:** Minimum 1GB available
- **Disk Space:** ~100MB for dependencies + your data

### Required Dependencies

All dependencies are already in `requirements.txt`. If you haven't installed them yet:

```bash
pip install -r requirements.txt
```

**Key Packages:**
- FastAPI >= 0.104.0
- SQLAlchemy >= 2.0.0
- uvicorn >= 0.24.0
- Jinja2 >= 3.1.2

### Database Setup

The dashboard uses SQLite, which requires no separate installation.

**First Time Setup:**

```bash
# Migrate existing JSON findings to database
python migrate_to_database.py --findings-dir output/findings --database output/findings.db
```

This will:
- Create `output/findings.db`
- Import all existing monitoring runs
- Preserve historical data

---

## Installation Guide

### Step 1: Clone/Navigate to Project

```bash
cd ~/Desktop/oc/agent
```

### Step 2: Activate Virtual Environment (if using)

```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Verify Installation

```bash
python -c "from dashboard.app import app; print('✅ Dashboard imports OK')"
```

### Step 5: Migrate Existing Data

```bash
python migrate_to_database.py
```

Expected output:
```
✅ Migration completed successfully!
Total runs: X
Total findings: Y
```

---

## Running the Dashboard

### Default Run (Port 8080)

```bash
python run_dashboard.py
```

Output:
```
╔═══════════════════════════════════════════════════════════════════╗
║        Operation Console Monitor - Web Dashboard                 ║
╚═══════════════════════════════════════════════════════════════════╝

🌐 Starting dashboard on http://0.0.0.0:8080
📖 API Documentation: http://0.0.0.0:8080/api/docs
⚙️  Configuration: config/monitor.yaml
```

### Custom Port

```bash
python run_dashboard.py --port 8888
```

### Custom Host

```bash
python run_dashboard.py --host 127.0.0.1 --port 8080
```

### Development Mode (Auto-reload)

```bash
python run_dashboard.py --reload
```

**Note:** Auto-reload is useful during development but should not be used in production.

### Custom Configuration

```bash
python run_dashboard.py --config /path/to/custom/monitor.yaml
```

---

## Command-Line Options

```bash
python run_dashboard.py [OPTIONS]
```

| Option | Description | Default |
|--------|-------------|---------|
| `--config` | Path to monitor.yaml | `config/monitor.yaml` |
| `--host` | Host to bind to | `0.0.0.0` |
| `--port` | Port to bind to | `8080` |
| `--reload` | Enable auto-reload | `False` |

### Examples

```bash
# Bind to localhost only
python run_dashboard.py --host 127.0.0.1

# Run on port 3000
python run_dashboard.py --port 3000

# Development mode with custom config
python run_dashboard.py --reload --config config/dev.yaml

# All options
python run_dashboard.py --host 0.0.0.0 --port 8080 --config config/monitor.yaml --reload
```

---

## Using the Dashboard

### Home Dashboard (/)

**Features:**
- System status indicator
- Quick statistics (3 cards)
  - Total monitoring runs
  - Active issues (critical + high)
  - Runs in last 24 hours
- Recent runs table (last 5 runs)
- Real-time updates (every 30 seconds)

**Actions:**
- Click any run row to view details
- View All Runs → Navigate to runs browser
- View Statistics → Navigate to statistics page

### API Documentation (/api/docs)

**Interactive Swagger UI:**
- Try all API endpoints
- View request/response schemas
- Test with real data
- Download OpenAPI spec

**Available Endpoints:**
- `GET /api/status` - System status
- `GET /api/runs` - List runs
- `GET /api/runs/{id}` - Run details
- `GET /api/runs/{id}/workflow-results` - Workflow results
- `GET /api/findings` - Search findings
- `GET /api/statistics` - Dashboard statistics
- `GET /health` - Health check

### Alternative API Docs (/api/redoc)

**ReDoc Interface:**
- Beautiful API documentation
- Markdown support
- Code samples
- Detailed schemas

---

## Testing the Dashboard

### 1. Health Check

```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "uptime_seconds": 123.45,
  "version": "1.0.0"
}
```

### 2. System Status

```bash
curl http://localhost:8080/api/status
```

Expected response:
```json
{
  "status": "idle",
  "last_run_id": "2026-06-30-190355",
  "last_run_timestamp": "2026-06-30T19:03:55",
  "last_run_status": "complete",
  "database_size_mb": 0.05
}
```

### 3. Statistics

```bash
curl http://localhost:8080/api/statistics
```

Expected response:
```json
{
  "total_runs": 1,
  "total_findings": 0,
  "severity_counts": {
    "Critical": 0,
    "High": 0,
    "Medium": 0,
    "Low": 0
  },
  "recent_runs_24h": 1,
  "critical_findings": 0,
  "high_findings": 0,
  "health_status": "healthy"
}
```

### 4. List Runs

```bash
curl http://localhost:8080/api/runs?page=1&page_size=5
```

### 5. Run Details

```bash
curl http://localhost:8080/api/runs/2026-06-30-190355
```

### 6. Workflow Results

```bash
curl http://localhost:8080/api/runs/2026-06-30-190355/workflow-results
```

---

## Running Alongside Monitoring

The dashboard can run **simultaneously** with the monitoring orchestrator:

### Terminal 1: Start Dashboard

```bash
python run_dashboard.py
```

### Terminal 2: Run Monitoring

```bash
# One-time run
python -m operation_console_monitor.orchestrator --config config/monitor.yaml

# Scheduled runs
python -m operation_console_monitor.scheduler --config config/monitor.yaml
```

**Both will access the same database**, so you'll see new runs appear in the dashboard in real-time!

---

## Production Deployment

### Using Uvicorn Directly

```bash
uvicorn dashboard.app:app --host 0.0.0.0 --port 8080 --workers 4
```

**Recommended for production:**
- Multiple workers for better performance
- Production-grade ASGI server
- Better resource management

### Using systemd (Linux)

Create `/etc/systemd/system/oc-dashboard.service`:

```ini
[Unit]
Description=Operation Console Monitor Dashboard
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/agent
ExecStart=/path/to/agent/.venv/bin/python run_dashboard.py --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable oc-dashboard
sudo systemctl start oc-dashboard
sudo systemctl status oc-dashboard
```

### Using Docker (Future)

```bash
# Build image
docker build -t oc-dashboard .

# Run container
docker run -d -p 8080:8080 \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/config:/app/config \
  --name oc-dashboard \
  oc-dashboard
```

---

## Troubleshooting

### Issue: Port Already in Use

**Error:**
```
OSError: [Errno 48] Address already in use
```

**Solution:**
```bash
# Check what's using port 8080
lsof -i :8080

# Kill the process
kill -9 <PID>

# Or use a different port
python run_dashboard.py --port 8888
```

### Issue: Database Not Found

**Error:**
```
sqlite3.OperationalError: unable to open database file
```

**Solution:**
```bash
# Create the database
python migrate_to_database.py

# Or ensure the path exists
mkdir -p output
```

### Issue: Import Errors

**Error:**
```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:**
```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep fastapi
```

### Issue: Database Lock

**Error:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
- SQLite is accessed by multiple processes
- Wait a moment and retry
- Database uses WAL mode which helps with concurrency
- If persistent, restart dashboard and orchestrator

### Issue: No Data Showing

**Problem:** Dashboard shows 0 runs, 0 findings

**Solution:**
```bash
# Check if database exists
ls -lh output/findings.db

# Check database contents
python -c "
from operation_console_monitor.database import DatabaseManager
db = DatabaseManager('output/findings.db')
print(f'Runs: {db.count_monitoring_runs()}')
"

# If empty, migrate data
python migrate_to_database.py
```

### Issue: Slow Performance

**Problem:** Dashboard is slow to load

**Possible Causes:**
1. Large database (many runs)
2. No indexes (check schema)
3. Single worker process

**Solutions:**
```bash
# Use multiple workers
uvicorn dashboard.app:app --workers 4

# Check database size
ls -lh output/findings.db

# Optimize database
sqlite3 output/findings.db "VACUUM;"
```

---

## Configuration

### Dashboard Section in monitor.yaml

```yaml
# Dashboard configuration
dashboard:
  enabled: true
  host: "0.0.0.0"           # Listen on all interfaces
  port: 8080                # Dashboard port
  reload: false             # Auto-reload (development only)
  workers: 1                # Number of worker processes
  database_path: "./output/findings.db"
  page_size: 50             # Items per page in lists
  screenshot_cache_ttl: 3600  # Cache TTL in seconds
  cors_origins: []          # CORS allowed origins (empty = same origin)
```

**Apply Changes:**

After editing `monitor.yaml`, restart the dashboard:
```bash
# Stop dashboard (Ctrl+C)
# Start again
python run_dashboard.py
```

---

## Performance Tips

### 1. Database Maintenance

```bash
# Vacuum database (reclaim space)
sqlite3 output/findings.db "VACUUM;"

# Analyze for better query planning
sqlite3 output/findings.db "ANALYZE;"
```

### 2. Multiple Workers

```bash
# For production, use multiple workers
uvicorn dashboard.app:app --host 0.0.0.0 --port 8080 --workers 4
```

### 3. Browser Caching

The dashboard automatically caches:
- Static assets (CSS, JS)
- API responses (client-side)

Clear browser cache if you see stale data.

---

## Accessing from Other Machines

### Local Network Access

If dashboard is running on `192.168.1.100`:

```bash
# Start with host 0.0.0.0 (listens on all interfaces)
python run_dashboard.py --host 0.0.0.0 --port 8080
```

Access from other machines:
- **URL:** http://192.168.1.100:8080
- **API:** http://192.168.1.100:8080/api/docs

### Firewall Rules

**macOS:**
```bash
# Allow incoming connections on port 8080
# System Preferences → Security & Privacy → Firewall → Firewall Options
```

**Linux (ufw):**
```bash
sudo ufw allow 8080/tcp
```

---

## Monitoring Dashboard Health

### Check if Running

```bash
# Health endpoint
curl http://localhost:8080/health

# Process check
ps aux | grep run_dashboard
```

### View Logs

Dashboard logs to stdout by default:

```bash
# Run in foreground to see logs
python run_dashboard.py

# Or redirect to file
python run_dashboard.py > dashboard.log 2>&1 &
```

### Monitor Resources

```bash
# CPU and memory usage
top -p $(pgrep -f run_dashboard)
```

---

## Stopping the Dashboard

### Graceful Shutdown

```bash
# Press Ctrl+C in the terminal
^C
INFO:     Shutting down
INFO:     Finished server process
```

### Force Stop

```bash
# Find process ID
ps aux | grep run_dashboard

# Kill process
kill -9 <PID>
```

---

## Next Steps

Once the dashboard is running:

1. **Explore the UI** - Navigate through pages
2. **Test API** - Use Swagger UI to try endpoints
3. **Run Monitoring** - Start orchestrator to generate new data
4. **Watch Real-time Updates** - Dashboard updates automatically

---

## Getting Help

### Check Logs

```bash
# Dashboard logs
python run_dashboard.py

# Look for errors or warnings
```

### Verify Configuration

```bash
# Check monitor.yaml syntax
python -c "import yaml; yaml.safe_load(open('config/monitor.yaml'))"
```

### Test Database

```bash
# Verify database is accessible
python -c "
from operation_console_monitor.database import DatabaseManager
db = DatabaseManager('output/findings.db')
stats = db.get_statistics()
print(f'✅ Database OK: {stats}')
"
```

---

## Summary

**Quick Commands:**

```bash
# Install dependencies
pip install -r requirements.txt

# Migrate data (first time only)
python migrate_to_database.py

# Start dashboard
python run_dashboard.py

# Open browser
open http://localhost:8080
```

**That's it!** The dashboard should now be running. 🎉

---

**Questions or Issues?**  
Check the troubleshooting section above or review the logs for error messages.

**Version:** 1.0.0  
**Last Updated:** 2026-06-30
