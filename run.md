# Run Guide

## 1. Prerequisites

- Python 3.11+
- Ollama installed
- Local Operation Console running (default config: `http://127.0.0.1:4173`)

## 2. Setup (from project root)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

Create runtime config files (first time only):

```bash
cp config/monitor.example.yaml config/monitor.yaml
cp config/.env.skyvern.example .env
```

Edit `config/monitor.yaml` and set:
- `operation_console_url`
- `ollama.model` (default: `qwen2.5vl:7b`)
- `schedule.mode`:
	- `one_time` for testing (run once and exit)
	- `interval` for continuous monitoring

If you want to use the included minimal OC-like website:

```bash
python -m http.server 4173 --directory mock_oc_site
```

## 3. Start Ollama + pull model

Start Ollama server in one terminal:

```bash
ollama serve
```

Pull model once (internet needed only first time):

```bash
ollama pull qwen2.5vl:7b
```

## 4. Run one monitoring cycle

```bash
python -m operation_console_monitor.orchestrator --config config/monitor.yaml
```

## 5. Run scheduled monitoring (continuous)

```bash
python -m operation_console_monitor.scheduler --config config/monitor.yaml
```

Notes:
- `schedule.mode: one_time` -> runs once and exits.
- `schedule.mode: interval` -> runs continuously every `schedule.interval_seconds`.

## 6. Output locations

- Screenshots: `output/screenshots/`
- JSON findings: `output/findings/`
- Logs: `output/logs/monitor.log`
- HTML page captures: `output/logs/page_captures/`

## 7. Offline mode note

After `ollama pull` completes, the full monitoring flow runs locally without external AI APIs or cloud keys.
