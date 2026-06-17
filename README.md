# Local-Only Operation Console Monitoring Prototype

This prototype runs fully on one machine and uses:

- **Skyvern (local mode)** for browser automation in Chromium
- **Ollama + Qwen 2.5 VL** for local screenshot/content analysis
- **Python orchestrator + scheduler** for recurring monitoring
- **Local storage** for screenshots, logs, and JSON findings

No OpenAI/Anthropic/Gemini API keys are required.

## Project structure

```text
.
├── config
│   ├── .env.skyvern.example
│   └── monitor.example.yaml
├── mock_oc_site
│   ├── index.html
│   └── styles.css
├── operation_console_monitor
│   ├── config.py
│   ├── logging_utils.py
│   ├── models.py
│   ├── ollama_analysis.py
│   ├── orchestrator.py
│   ├── scheduler.py
│   └── skyvern_capture.py
├── output
│   ├── findings
│   ├── logs
│   └── screenshots
├── requirements.txt
└── samples
    └── finding.sample.json
```

## Architecture

Operation Console (localhost) -> Skyvern -> Chromium -> screenshot/page capture -> Ollama (local) -> Qwen 2.5 VL -> JSON findings + local artifacts

## Local setup

1. Create and activate a Python 3.11+ environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install Chromium for Playwright:
   ```bash
   python -m playwright install chromium
   ```
4. Install and start Ollama:
   ```bash
   ollama serve
   ```
5. Pull model once (internet needed only here):
   ```bash
   ollama pull qwen2.5vl:7b
   ```
6. Create runtime files:
   ```bash
   cp config/monitor.example.yaml config/monitor.yaml
   cp config/.env.skyvern.example .env
   ```
7. Update `config/monitor.yaml` with your local Operation Console URL.

Optional: use the included mock OC-style site on port `4173`:

```bash
python -m http.server 4173 --directory mock_oc_site
```

After the model is downloaded, this setup can run offline.

By default, each run performs a short preflight check against `operation_console_url`
before launching browser capture. This reduces transient failures when the console
process starts a few seconds late.

## Run the monitoring workflow

Run one monitoring cycle:

```bash
python -m operation_console_monitor.orchestrator --config config/monitor.yaml
```

Run recurring monitoring:

```bash
python -m operation_console_monitor.scheduler --config config/monitor.yaml
```

## What each run produces

- Screenshot: `output/screenshots/<run_id>.png`
- Page capture HTML: `output/logs/page_captures/<run_id>.html`
- Findings JSON: `output/findings/<run_id>.json`
- Runtime logs: `output/logs/monitor.log`

## JSON finding shape

Each finding entry follows this shape:

```json
{
  "timestamp": "2026-06-15T10:00:00",
  "severity": "High",
  "issue": "Failed jobs detected",
  "recommendation": "Investigate scheduler service and retry failed jobs.",
  "screenshot": "output/screenshots/2026-06-15-100000.png"
}
```

A full sample report is included at `samples/finding.sample.json`.

## Troubleshooting

### 1) `Skyvern is not installed`

Install Skyvern local extras:

```bash
pip install "skyvern[local]"
```

### 2) Browser launch fails

- Ensure Chromium is installed:
  ```bash
  python -m playwright install chromium
  ```
- If running headful mode on a server, set `skyvern.headless: true`.

### 2.1) `ERR_CONNECTION_REFUSED` on Operation Console URL

- Ensure the console service is running and reachable at `operation_console_url`.
- Tune preflight retries in `config/monitor.yaml`:
   - `preflight.max_attempts`
   - `preflight.request_timeout_seconds`
   - `preflight.retry_delay_seconds`

### 3) Ollama connection errors

- Confirm Ollama is running on `http://127.0.0.1:11434`:
  ```bash
  ollama list
  ```
- Verify `ollama.base_url` in `config/monitor.yaml`.

### 4) Model not found

Pull the configured model:

```bash
ollama pull qwen2.5vl:7b
```

### 5) Empty or low-quality findings

- Increase `ollama.max_page_content_chars` in config.
- Increase `skyvern.wait_after_load_seconds` if dashboard widgets load slowly.
- Use a stronger vision-capable local model if available.
