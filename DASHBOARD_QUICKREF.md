# Dashboard Quick Reference

**Quick start guide for Operation Console Monitor Dashboard**

---

## 🚀 Quick Start (3 Steps)

```bash
# 1. Migrate data (first time only)
python migrate_to_database.py

# 2. Start dashboard
python run_dashboard.py

# 3. Open browser
open http://localhost:8080
```

---

## 📋 Common Commands

```bash
# Start dashboard
python run_dashboard.py

# Custom port
python run_dashboard.py --port 8888

# Development mode (auto-reload)
python run_dashboard.py --reload

# Production mode (multiple workers)
uvicorn dashboard.app:app --host 0.0.0.0 --port 8080 --workers 4

# Stop dashboard
Ctrl+C  (or kill -9 <PID>)
```

---

## 🌐 URLs

| Page | URL |
|------|-----|
| Home Dashboard | http://localhost:8080 |
| API Docs (Swagger) | http://localhost:8080/api/docs |
| API Docs (ReDoc) | http://localhost:8080/api/redoc |
| Health Check | http://localhost:8080/health |

---

## 🔌 API Endpoints

```bash
# System status
curl http://localhost:8080/api/status

# Statistics
curl http://localhost:8080/api/statistics

# List runs
curl http://localhost:8080/api/runs?page=1&page_size=5

# Get run details
curl http://localhost:8080/api/runs/2026-06-30-190355

# Workflow results
curl http://localhost:8080/api/runs/2026-06-30-190355/workflow-results

# Search findings
curl http://localhost:8080/api/findings?severity=Critical&page=1

# Health check
curl http://localhost:8080/health
```

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| Port in use | `python run_dashboard.py --port 8888` |
| No data showing | `python migrate_to_database.py` |
| Import errors | `pip install -r requirements.txt` |
| Database locked | Wait or restart both dashboard & orchestrator |

---

## 🔧 Configuration

Edit `config/monitor.yaml`:

```yaml
dashboard:
  host: "0.0.0.0"
  port: 8080
  database_path: "./output/findings.db"
  page_size: 50
```

Restart dashboard after changes.

---

## 📊 Database Operations

```bash
# Migrate existing data
python migrate_to_database.py

# Check database
ls -lh output/findings.db

# Optimize database
sqlite3 output/findings.db "VACUUM;"

# Check contents
python -c "from operation_console_monitor.database import DatabaseManager; \
db = DatabaseManager('output/findings.db'); \
print(f'Runs: {db.count_monitoring_runs()}')"
```

---

## 🏃 Running with Monitoring

**Terminal 1:**
```bash
python run_dashboard.py
```

**Terminal 2:**
```bash
# One-time
python -m operation_console_monitor.orchestrator --config config/monitor.yaml

# Scheduled
python -m operation_console_monitor.scheduler --config config/monitor.yaml
```

Both use same database - see updates in real-time!

---

## 🎯 Features Available

✅ Real-time system status  
✅ Statistics dashboard  
✅ Recent runs table  
✅ Paginated runs list  
✅ Run details view  
✅ Workflow results (OC mode)  
✅ Findings search  
✅ Auto-refresh (30s)  
✅ API documentation  
✅ Health monitoring  

---

## 📱 Access from Other Devices

```bash
# Start on all interfaces
python run_dashboard.py --host 0.0.0.0

# Access from other machines
http://<your-ip>:8080
```

---

## 🔒 Security Notes

- Currently: **No authentication** (local network only)
- Use firewall to restrict access
- Don't expose to public internet yet

---

**For full documentation, see:** `DASHBOARD_GUIDE.md`
