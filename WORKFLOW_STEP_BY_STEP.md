# Operation Console Monitor: Step-by-Step Runtime Flow

This document explains exactly what the command does from start to end:

python -m operation_console_monitor.orchestrator --config config/monitor.yaml

The runtime path depends on execution_mode in config/monitor.yaml:
- monitor
- oc_workflow

## 0. Common startup sequence (always runs first)

1. Load environment values from .env if present.
2. Load YAML config from config/monitor.yaml.
3. Ensure output folders exist:
   - output/screenshots
   - output/findings
   - output/logs
   - output/logs/page_captures
   - output/downloads
4. Create a new run_id timestamp (for file naming).
5. Run preflight URL check to operation_console_url.
   - Default target in this repo: http://127.0.0.1:4173
   - If preflight fails after retries, run exits with error.

---

## 1. Path A: monitor mode (execution_mode: monitor)

This is the lightweight page-capture + Ollama analysis flow.

### Page navigation and actions

1. Open Chromium via Playwright.
2. Go to operation_console_url.
3. Wait for page load + configured wait_after_load_seconds.
4. Capture main page artifacts:
   - Full-page screenshot
   - Full page HTML
5. Scan the current page for unhealthy indicators using keywords:
   - degraded, critical, failed, down, unhealthy, error
6. For each matching clickable candidate:
   - Click candidate
   - Confirm actual navigation (URL or title changed)
   - Capture detail-page screenshot + HTML metadata
   - Go back to main page
7. Run Ollama analysis on:
   - Main screenshot
   - Any degraded/detail screenshots
   - Page HTML context
8. Normalize findings and write outputs:
   - output/findings/<run_id>.json
   - output/findings/summary.json
   - Optional per-service JSON files (for degraded detail pages)

### Pages it usually visits

1. Main dashboard URL from operation_console_url.
2. Zero or more service detail pages reached from unhealthy widgets/rows.
3. Back to main dashboard between detail captures.

---

## 2. Path B: oc_workflow mode (execution_mode: oc_workflow)

This is the full multi-step investigation workflow with customer loop.

### Step-by-step sequence (1 to last)

1. Open operation_console_url in Chromium.
2. Click SSO sign-in button.
3. Wait for dashboard shell (dashboard URL or monitoring marker).

If STEP_1=true (or default):
4. Open Monitoring.
5. Apply filters:
   - ED Status: OK
   - ED Service Status: Major/Critical
   - ED Condition: Subscription and Smart COM
6. Download monitoring CSV.
7. Read CSV and select customers in configured window_hours (default 24h).
8. If none found in strict window, fallback to CSV list without time window.

If STEP_2=true:
9. Skip filter/download phase and reuse latest CSV from output/downloads.
10. Build customer list from CSV (same time-window logic).

For each customer (loop):
11. Go to Monitoring -> Account Monitoring.
12. Search customer name.
13. Capture evidence screenshot(s) in Account Monitoring.
14. Validate component/service status in Account Monitoring:
   - Proceed only if component/service status shows Major Problem.
   - If not Major Problem, skip customer.
15. Open Readkit Status and validate eligibility:
   - Proceed only when KOP/RK/ED status is explicitly OK.
   - If any of KOP/RK/ED is not OK (or status is unclear), skip customer.
16. Open Service Status and extract:
   - adapter_id
   - datapoint-like text
17. Go to Monitoring -> DAS Validation.
18. Search adapter_id and open row detail.
19. Capture DAS evidence before filtering.
20. Apply STATE filter = faulted.
21. Extract error datapoints and source IDs.
22. Validate source ID match between Account Monitoring and DAS rows.
23. Capture DAS filtered evidence.
24. Datapoint eligibility gate:
   - If reference list exists, call Ollama to check match.
   - If mismatch, skip customer.
25. Go to Monitoring -> SSM.
26. Run ping command (ping -c3 <machine_ip>) and check output.
   - If ping fails, classify Host Unreachable - Ping Failed.
27. Go to Monitoring -> Connectivity Check.
28. Run connectivity checks.
29. Final classification:
   - Any failed/red indicator -> NOC Report - Port Issue
   - Otherwise -> NOC Report - Onsite Issue

End of run:
30. Write primary workflow JSON: output/findings/<run_id>.json
31. Write workflow step export:
   - output/findings/<run_id>-workflow-steps.csv
   - output/findings/<run_id>-workflow-steps.xlsx (if openpyxl available)
32. Write rolling summary: output/findings/summary.json

### Pages it visits in oc_workflow

1. Login or landing page at operation_console_url.
2. Dashboard shell after SSO.
3. Monitoring section.
4. Account Monitoring sub-page.
5. Readkit Status tab (inside account view).
6. Service Status tab (inside account view).
7. DAS Validation page.
8. SSM page.
9. Connectivity Check page.

It moves between those pages repeatedly for each customer in the loop.

---

## 3. Why preflight failed in your recent run

Your log showed preflight retries and then failure. That means operation_console_url was unreachable at that moment.

For local mock usage, start server from agent directory with:

python3 -m http.server 4173 --directory mock_oc_site

Then run orchestrator from agent directory.