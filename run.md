# Run Guide

## 1. Prerequisites

- Python 3.11+
- Ollama installed
- Local Operation Console running (default config: `http://127.0.0.1:4173`)

## 2. Setup (from agent project root)

Run all commands below from `oc/agent` unless noted otherwise.

```bash
cd agent
```

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
chmod +x run_local
./run_local
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

Start the mock OC site:

If you are in `oc/agent`:

```bash
python3 -m http.server 4173 --directory mock_oc_site
```

If you are in workspace root (`oc`):

```bash
python3 -m http.server 4173 --directory agent/mock_oc_site
```



## 4. Run one monitoring cycle

```bash
python -m operation_console_monitor.orchestrator --config config/monitor.yaml
```

If you are staying in workspace root (`oc`), use:

```bash
PYTHONPATH=agent python -m operation_console_monitor.orchestrator --config agent/config/monitor.yaml
```

## 5. Run scheduled monitoring (continuous)

```bash
python -m operation_console_monitor.scheduler --config config/monitor.yaml
```

If you are staying in workspace root (`oc`), use:

```bash
PYTHONPATH=agent python -m operation_console_monitor.scheduler --config agent/config/monitor.yaml
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

## 8. Full step-by-step workflow document

For full runtime sequence (which page it visits, what each step does from start to finish), see:

- `WORKFLOW_STEP_BY_STEP.md`
