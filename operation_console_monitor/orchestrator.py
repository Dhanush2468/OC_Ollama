from __future__ import annotations

import argparse
import json
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


def _run_once(config_path: str) -> int:
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

    if str(config.execution_mode).strip().lower() == "oc_workflow":
        try:
            payload = run_oc_workflow(config=config, run_id=run_id, timestamp=timestamp)
            with open(findings_path, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2)

            results = payload.get("results", [])
            noc_report_customers = []
            for item in results:
                status = str(item.get("status", "")).strip().lower()
                outcome = str(item.get("outcome", "")).strip()
                customer_name = str(item.get("customer_name", "")).strip()

                # Customers that reached final outcome classification and require NOC reporting.
                if status == "investigated" and outcome.startswith("NOC Report"):
                    noc_report_customers.append(
                        {
                            "customer_name": customer_name,
                            "outcome": outcome,
                            "machine_ip": str(item.get("machine_ip", "")).strip(),
                            "adapter_id": str(item.get("adapter_id", "")).strip(),
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
                        "noc_report_count": len(noc_report_customers),
                        "noc_report_customers": noc_report_customers,
                    },
                    file,
                    indent=2,
                )
            logger.info("OC workflow run completed: %s", findings_path)
            print(findings_path)
            return 0
        except Exception as exc:
            logger.exception("OC workflow run failed: %s", exc)
            return 1

    try:
        capture_result = capture_console_page(config, screenshot_path, page_capture_path)
    except Exception as exc:
        logger.exception("Capture failed: %s", exc)
        return 1

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one operation console monitoring cycle")
    parser.add_argument("--config", required=True, help="Path to monitor.yaml")
    args = parser.parse_args()
    return _run_once(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
