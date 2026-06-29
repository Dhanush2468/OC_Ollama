from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from time import sleep
from urllib import request

from .config import ensure_output_directories, load_config
from .logging_utils import build_logger
from .models import Finding, MonitoringReport
from .oc_workflow import run_oc_workflow
from .ollama_analysis import analyze_page
from .skyvern_capture import capture_console_page


# -----------------------------------------------------------------------------
# Environment and preflight helpers
# -----------------------------------------------------------------------------
def _load_runtime_env() -> None:
    """Load simple KEY=VALUE pairs from .env when not already exported."""
    candidate_paths = [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]

    env_path: Path | None = None
    for candidate in candidate_paths:
        if candidate.exists() and candidate.is_file():
            env_path = candidate
            break

    if env_path is None:
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# Poll the console URL before running browser automation.
def _wait_for_console(config, logger) -> bool:
    if not config.preflight.enabled:
        return True

    attempts = max(1, config.preflight.max_attempts)
    timeout = max(1, config.preflight.request_timeout_seconds)
    delay = max(1, config.preflight.retry_delay_seconds)

    for attempt in range(1, attempts + 1):
        try:
            with request.urlopen(config.operation_console_url, timeout=timeout) as response:
                if response.status < 500:
                    logger.info("Preflight succeeded on attempt %s", attempt)
                    return True
        except Exception:
            pass

        if attempt < attempts:
            logger.info("Preflight attempt %s/%s failed, retrying in %ss", attempt, attempts, delay)
            sleep(delay)

    logger.error("Preflight failed after %s attempts", attempts)
    return False


# -----------------------------------------------------------------------------
# Export helpers (workflow mode)
# -----------------------------------------------------------------------------
# Convert list-like values into flat text for CSV/XLSX export cells.
def _flatten_value(value) -> str:
    if isinstance(value, list):
        return "; ".join(str(item).strip() for item in value if str(item).strip())
    if value is None:
        return ""
    return str(value).strip()


# Build tabular step-by-step rows from workflow JSON payload.
def _build_oc_workflow_step_export_rows(payload: dict) -> tuple[list[str], list[dict[str, str]]]:
    results = payload.get("results", [])
    if not isinstance(results, list):
        return [], []

    ordered_step_names: list[str] = []
    seen_steps: set[str] = set()
    for result in results:
        steps = result.get("steps", []) if isinstance(result, dict) else []
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_name = str(step.get("name", "")).strip()
            if not step_name or step_name in seen_steps:
                continue
            seen_steps.add(step_name)
            ordered_step_names.append(step_name)

    headers = [
        "customer_name",
        "timestamp_iso",
        "status",
        "outcome",
        "adapter_id",
        "machine_ip",
        "matched_datapoints",
        "error_datapoints",
    ]
    for step_name in ordered_step_names:
        headers.append(f"{step_name}_status")
        headers.append(f"{step_name}_details")

    rows: list[dict[str, str]] = []
    for result in results:
        if not isinstance(result, dict):
            continue

        row: dict[str, str] = {
            "customer_name": _flatten_value(result.get("customer_name")),
            "timestamp_iso": _flatten_value(result.get("timestamp_iso")),
            "status": _flatten_value(result.get("status")),
            "outcome": _flatten_value(result.get("outcome")),
            "adapter_id": _flatten_value(result.get("adapter_id")),
            "machine_ip": _flatten_value(result.get("machine_ip")),
            "matched_datapoints": _flatten_value(result.get("matched_datapoints")),
            "error_datapoints": _flatten_value(result.get("error_datapoints")),
        }

        steps = result.get("steps", [])
        step_lookup: dict[str, dict] = {}
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                step_name = str(step.get("name", "")).strip()
                if step_name and step_name not in step_lookup:
                    step_lookup[step_name] = step

        for step_name in ordered_step_names:
            step_data = step_lookup.get(step_name, {})
            row[f"{step_name}_status"] = _flatten_value(step_data.get("status"))
            row[f"{step_name}_details"] = _flatten_value(step_data.get("details"))

        rows.append(row)

    return headers, rows


# Write workflow step report to CSV and optional XLSX.
def _export_oc_workflow_spreadsheet(payload: dict, findings_dir: str, run_id: str, logger) -> tuple[str, str]:
    headers, rows = _build_oc_workflow_step_export_rows(payload)
    if not headers or not rows:
        return "", ""

    base_path = Path(findings_dir) / f"{run_id}-workflow-steps"
    csv_path = str(base_path.with_suffix(".csv"))
    xlsx_path = ""

    with open(csv_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    try:
        from openpyxl import Workbook

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "workflow_steps"
        worksheet.append(headers)
        for row in rows:
            worksheet.append([row.get(header, "") for header in headers])

        xlsx_path = str(base_path.with_suffix(".xlsx"))
        workbook.save(xlsx_path)
    except Exception as exc:
        logger.warning("XLSX export skipped, openpyxl unavailable: %s", exc)

    return csv_path, xlsx_path


# -----------------------------------------------------------------------------
# Single-run orchestrator
# -----------------------------------------------------------------------------
# Coordinates config load, execution mode routing, capture, analysis, and outputs.
def _run_once(config_path: str) -> int:
    # Step 1: Setup runtime context (env, config, logger, output paths).
    _load_runtime_env()
    config = load_config(config_path)
    ensure_output_directories(config)
    logger = build_logger(config.paths.logs_dir)

    run_id = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    timestamp = datetime.now().isoformat(timespec="seconds")

    screenshot_path = str(Path(config.paths.screenshots_dir) / f"{run_id}.png")
    page_capture_path = str(Path(config.paths.page_capture_dir) / f"{run_id}.html")
    findings_path = str(Path(config.paths.findings_dir) / f"{run_id}.json")

    logger.info("Starting monitor run %s", run_id)
    if not _wait_for_console(config, logger):
        return 1

    # Step 2: Route to OC workflow mode when configured.
    if str(config.execution_mode).strip().lower() == "oc_workflow":
        try:
            payload = run_oc_workflow(config=config, run_id=run_id, timestamp=timestamp)
            with open(findings_path, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2)

            workflow_csv_path, workflow_xlsx_path = _export_oc_workflow_spreadsheet(
                payload=payload,
                findings_dir=config.paths.findings_dir,
                run_id=run_id,
                logger=logger,
            )

            results = payload.get("results", [])
            noc_report_customers = []
            for item in results:
                status = str(item.get("status", "")).strip().lower()
                outcome = str(item.get("outcome", "")).strip()
                customer_name = str(item.get("customer_name", "")).strip()

                # Customers that reached final outcome classification and require NOC reporting.
                if status == "investigated" and outcome.startswith("NOC Report"):
                    account_evidence = str(item.get("evidence_account_monitoring_screenshot", "")).strip()
                    account_service_evidence = str(
                        item.get("evidence_account_monitoring_service_status_screenshot", "")
                    ).strip()
                    account_das_service_evidence = str(
                        item.get("evidence_account_monitoring_das_service_status_screenshot", "")
                    ).strip()
                    das_all_rows_evidence = str(item.get("evidence_das_validation_all_rows_screenshot", "")).strip()
                    das_evidence = str(item.get("evidence_das_validation_screenshot", "")).strip()
                    das_source_id_match = item.get("evidence_das_validation_source_id_match")
                    observed_source_ids_raw = item.get("evidence_das_validation_observed_source_ids", [])
                    observed_source_ids = (
                        [str(value).strip() for value in observed_source_ids_raw if str(value).strip()]
                        if isinstance(observed_source_ids_raw, list)
                        else []
                    )
                    noc_report_customers.append(
                        {
                            "customer_name": customer_name,
                            "outcome": outcome,
                            "machine_ip": str(item.get("machine_ip", "")).strip(),
                            "adapter_id": str(item.get("adapter_id", "")).strip(),
                            "evidence": {
                                "account_monitoring_datapoints_screenshot": account_evidence,
                                "account_monitoring_service_status_screenshot": account_service_evidence,
                                "account_monitoring_das_service_status_screenshot": account_das_service_evidence,
                                "das_validation_all_rows_screenshot": das_all_rows_evidence,
                                "das_validation_endpoints_screenshot": das_evidence,
                                "das_validation_source_id_match": das_source_id_match,
                                "das_validation_observed_source_ids": observed_source_ids,
                            },
                        }
                    )

            summary_path = Path(config.paths.findings_dir) / "summary.json"
            with open(summary_path, "w", encoding="utf-8") as file:
                json.dump(
                    {
                        "run_id": run_id,
                        "timestamp": timestamp,
                        "execution_mode": "oc_workflow",
                        "customers_in_window": int(payload.get("customers_in_window", 0)),
                        "investigated_customers": int(payload.get("investigated_customers", 0)),
                        "downloaded_csv": str(payload.get("downloaded_csv", "")),
                        "workflow_steps_csv": workflow_csv_path,
                        "workflow_steps_xlsx": workflow_xlsx_path,
                        "noc_report_count": len(noc_report_customers),
                        "noc_report_customers": noc_report_customers,
                    },
                    file,
                    indent=2,
                )
            if workflow_csv_path:
                logger.info("OC workflow CSV export completed: %s", workflow_csv_path)
            if workflow_xlsx_path:
                logger.info("OC workflow XLSX export completed: %s", workflow_xlsx_path)
            logger.info("OC workflow run completed: %s", findings_path)
            print(findings_path)
            return 0
        except Exception as exc:
            logger.exception("OC workflow run failed: %s", exc)
            return 1

    # Step 3: Default monitor mode - capture console page artifacts.
    try:
        capture_result = capture_console_page(config, screenshot_path, page_capture_path)
    except Exception as exc:
        logger.exception("Capture failed: %s", exc)
        return 1

    # Step 4: Run Ollama analysis against captured artifacts.
    try:
        degraded_views = capture_result.get("degraded_views", [])
        screenshot_paths = [screenshot_path] + [
            str(item.get("screenshot_path", "")) for item in degraded_views if item.get("screenshot_path")
        ]
        analysis = analyze_page(
            config,
            screenshot_paths=screenshot_paths,
            page_title=capture_result.get("page_title", ""),
            page_url=capture_result.get("page_url", config.operation_console_url),
            page_html=capture_result.get("html", ""),
            degraded_views=degraded_views,
        )
    except Exception as exc:
        logger.exception("Analysis failed: %s", exc)
        return 1

    # Step 5: Normalize findings into dataclass objects.
    findings = []
    for item in analysis.get("findings", []):
        findings.append(
            Finding(
                timestamp=timestamp,
                severity=str(item.get("severity", "Unknown")),
                issue=str(item.get("issue", "Unspecified issue")),
                recommendation=str(item.get("recommendation", "No recommendation")),
                evidence=str(item.get("evidence", "")),
                screenshot=str(item.get("screenshot", screenshot_path)),
                details=str(item.get("details", "")),
                source_view=str(item.get("source_view", "main")),
            )
        )

    # Step 6: Persist per-service JSON files for degraded detail pages.
    degraded_screenshots = [
        str(item.get("screenshot_path", "")) for item in capture_result.get("degraded_views", []) if item.get("screenshot_path")
    ]
    service_json_files = []

    for view in degraded_views:
        service_name = str(view.get("service_name", "")).strip()
        service_suffix = str(view.get("service_suffix", "")).strip()
        if not service_suffix:
            continue

        per_service_findings = [
            item
            for item in findings
            if str(item.source_view).strip().lower() == service_name.lower()
            or service_name.lower() in str(item.source_view).strip().lower()
        ]

        service_json_path = str(Path(config.paths.findings_dir) / f"{run_id}-{service_suffix}.json")
        payload = {
            "run_id": run_id,
            "timestamp": timestamp,
            "service_name": service_name,
            "service_suffix": service_suffix,
            "service_label": str(view.get("label", "")),
            "service_keyword": str(view.get("keyword", "")),
            "service_page_url": str(view.get("page_url", "")),
            "service_page_title": str(view.get("page_title", "")),
            "service_screenshot": str(view.get("screenshot_path", "")),
            "overall_status": str(analysis.get("overall_status", "unknown")),
            "summary": str(analysis.get("summary", "No summary provided")),
            "summary_insights": [str(item) for item in analysis.get("summary_insights", [])],
            "findings": [item.__dict__ for item in per_service_findings],
        }
        with open(service_json_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
        service_json_files.append(service_json_path)

    # Step 7: Persist consolidated report and rolling summary.
    report = MonitoringReport(
        run_id=run_id,
        timestamp=timestamp,
        console_url=config.operation_console_url,
        page_url=capture_result.get("page_url", config.operation_console_url),
        page_title=capture_result.get("page_title", ""),
        overall_status=str(analysis.get("overall_status", "unknown")),
        summary=str(analysis.get("summary", "No summary provided")),
        summary_insights=[str(item) for item in analysis.get("summary_insights", [])],
        findings=findings,
        page_capture_html=page_capture_path,
        degraded_screenshots=degraded_screenshots,
    )

    with open(findings_path, "w", encoding="utf-8") as file:
        json.dump(report.to_dict(), file, indent=2)

    summary_path = Path(config.paths.findings_dir) / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as file:
        json.dump(
            {
                "run_id": run_id,
                "timestamp": timestamp,
                "overall_status": report.overall_status,
                "summary": report.summary,
                "summary_insights": report.summary_insights,
                "findings_count": len(findings),
                "degraded_screenshots": degraded_screenshots,
                "service_json_files": service_json_files,
            },
            file,
            indent=2,
        )

    logger.info("Run completed: %s", findings_path)
    print(findings_path)
    return 0


# CLI entrypoint for one-cycle execution.
def main() -> int:
    parser = argparse.ArgumentParser(description="Run one operation console monitoring cycle")
    parser.add_argument("--config", required=True, help="Path to monitor.yaml")
    args = parser.parse_args()
    return _run_once(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
