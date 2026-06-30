# Local-Only Operation Console Monitoring Prototype

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A fully local monitoring solution for operation consoles that requires no cloud APIs or external dependencies (except for initial model download).

## Features

- **🔒 Privacy-First**: Runs entirely on your machine - no data leaves your network
- **🤖 AI-Powered Analysis**: Uses Ollama + Qwen 2.5 VL for intelligent screenshot and content analysis
- **🌐 Browser Automation**: Leverages Skyvern and Playwright for reliable web interaction
- **📊 Automated Workflow**: Python-based orchestration with configurable scheduling
- **💾 Local Storage**: All artifacts (screenshots, logs, findings) stored locally

## Technology Stack

- **Skyvern** (local mode) - Browser automation in Chromium
- **Ollama + Qwen 2.5 VL** - Local screenshot and content analysis
- **Python 3.11+** - Orchestrator and scheduler
- **APScheduler** - Recurring monitoring tasks
- **Playwright** - Web browser control

## Project Structure

```text
.
├── config/
│   ├── .env.skyvern.example      # Environment variables template
│   └── monitor.example.yaml      # Configuration template
├── mock_oc_site/
│   ├── index.html                # Mock operation console for testing
│   └── styles.css
├── operation_console_monitor/
│   ├── __init__.py               # Package initialization
│   ├── config.py                 # Configuration management
│   ├── logging_utils.py          # Logging setup
│   ├── models.py                 # Data models
│   ├── ollama_analysis.py        # AI analysis integration
│   ├── orchestrator.py           # Main workflow orchestration
│   ├── scheduler.py              # Task scheduling
│   ├── skyvern_capture.py        # Browser automation
│   └── oc_workflow.py            # OC-specific workflow logic
├── output/
│   ├── findings/                 # JSON analysis results
│   ├── logs/                     # Runtime logs
│   └── screenshots/              # Captured images
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Architecture

```
Operation Console (localhost)
    ↓
Skyvern → Chromium → screenshot/page capture
    ↓
Ollama (local) → Qwen 2.5 VL
    ↓
JSON findings + local artifacts
```

## Installation

### Prerequisites

- Python 3.11 or higher
- ~8GB RAM (for Ollama model)
- Internet connection (for initial setup only)

### Step 1: Python Environment

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Browser Setup

```bash
# Install Chromium for Playwright
python -m playwright install chromium
```

### Step 3: Ollama Setup

```bash
# Install Ollama (visit https://ollama.ai for OS-specific instructions)

# Start Ollama service
ollama serve

# Pull the vision model (requires internet, ~4GB download)
ollama pull qwen2.5vl:7b
```

### Step 4: Configuration

```bash
# Copy configuration templates
cp config/monitor.example.yaml config/monitor.yaml
cp config/.env.skyvern.example .env

# Edit config/monitor.yaml with your Operation Console URL
```

## Configuration

Edit `config/monitor.yaml` to customize:

```yaml
# Target URL
operation_console_url: "http://localhost:4173"

# Execution mode: "monitor" or "oc_workflow"
execution_mode: "monitor"

# Preflight checks (optional)
preflight:
  enabled: true
  max_attempts: 5
  request_timeout_seconds: 3
  retry_delay_seconds: 2

# Scheduling
schedule:
  mode: "interval"          # "interval" or "one_time"
  interval_seconds: 300     # 5 minutes
  timezone: "UTC"

# Browser settings
skyvern:
  headless: true
  wait_after_load_seconds: 2
  navigation_timeout_seconds: 45
  viewport_width: 1920
  viewport_height: 1080

# AI model settings
ollama:
  base_url: "http://127.0.0.1:11434"
  model: "qwen2.5vl:7b"
  timeout_seconds: 180
  max_page_content_chars: 12000
  vision_enabled: true

# Analysis settings
analysis:
  max_findings: 5
```

## Usage

### One-Time Monitoring Run

```bash
python -m operation_console_monitor.orchestrator --config config/monitor.yaml
```

### Recurring Monitoring (Scheduled)

```bash
python -m operation_console_monitor.scheduler --config config/monitor.yaml
```

### Test with Mock Console

```bash
# Start mock operation console on port 4173
python -m http.server 4173 --directory mock_oc_site

# In another terminal, run monitor
python -m operation_console_monitor.orchestrator --config config/monitor.yaml
```

## Output

Each monitoring run produces:

| Artifact | Location | Description |
|----------|----------|-------------|
| Screenshot | `output/screenshots/<run_id>.png` | Full-page screenshot of console |
| HTML Capture | `output/logs/page_captures/<run_id>.html` | Page HTML snapshot |
| Findings JSON | `output/findings/<run_id>.json` | Structured analysis results |
| Summary | `output/findings/summary.json` | Latest run summary |
| Logs | `output/logs/monitor.log` | Runtime execution logs |

### JSON Finding Structure

```json
{
  "run_id": "2026-06-30-161130",
  "timestamp": "2026-06-30T16:11:30",
  "overall_status": "critical",
  "summary": "3 critical issues detected requiring immediate attention",
  "summary_insights": [
    "Multiple services in degraded state",
    "High error rate on authentication service"
  ],
  "findings": [
    {
      "timestamp": "2026-06-30T16:11:30",
      "severity": "High",
      "issue": "Failed jobs detected",
      "recommendation": "Investigate scheduler service and retry failed jobs",
      "evidence": "15 jobs in failed state",
      "screenshot": "output/screenshots/2026-06-30-161130.png",
      "details": "Jobs failing since 14:30 UTC",
      "source_view": "main"
    }
  ]
}
```

## Troubleshooting

### Skyvern Not Installed

```bash
pip install "skyvern[local]"
```

### Browser Launch Fails

```bash
# Install Chromium
python -m playwright install chromium

# For headless server environments
# Set skyvern.headless: true in config/monitor.yaml
```

### Connection Refused on Console URL

1. Verify the console service is running
2. Check `operation_console_url` in config
3. Adjust preflight settings in config:
   - `preflight.max_attempts`
   - `preflight.request_timeout_seconds`
   - `preflight.retry_delay_seconds`

### Ollama Connection Errors

```bash
# Check if Ollama is running
ollama list

# Verify base_url in config/monitor.yaml
# Default: http://127.0.0.1:11434
```

### Model Not Found

```bash
# Pull the configured model
ollama pull qwen2.5vl:7b

# Verify model name matches config
ollama list
```

### Empty or Low-Quality Findings

- Increase `ollama.max_page_content_chars` in config
- Increase `skyvern.wait_after_load_seconds` if widgets load slowly
- Try a more powerful vision model if available:
  ```bash
  ollama pull qwen2.5vl:32b  # Requires more RAM
  ```

## Offline Operation

After initial setup (model download), this system runs completely offline:

1. ✅ Browser automation (Playwright)
2. ✅ Screenshot capture
3. ✅ AI analysis (Ollama)
4. ✅ Report generation

No internet connection required for normal operation.

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request with clear description

## Author

**Dhanush.V**

---

**Note**: By default, preflight checks ensure the console is reachable before launching browser automation. This reduces transient failures when services start with delays.
