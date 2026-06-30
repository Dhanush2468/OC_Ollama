from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import re
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Iterable
from urllib import request

from .config import MonitorConfig
from .models import CustomerInvestigationResult, OCWorkflowReport, StepResult


# -----------------------------------------------------------------------------
# Time parsing utilities
# -----------------------------------------------------------------------------
TIME_FORMATS = (
    "%B %d, %Y at %I:%M:%S %p",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d-%m-%Y %H:%M",
    "%d/%m/%Y %H:%M",
    "%Y/%m/%d %H:%M:%S",
)


# Parse mixed timestamp formats seen across real/mock CSV exports.
def _parse_time(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None

    normalized = text
    if "Last Seen:" in normalized:
        normalized = normalized.split("Last Seen:", 1)[1].strip()

    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


# Load reference datapoints from .txt or .json for validation gating.
def _load_reference_datapoints(path: str) -> set[str]:
    if not path:
        return set()

    file_path = Path(path)
    if not file_path.exists():
        return set()

    if file_path.suffix.lower() == ".json":
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(item).strip().lower() for item in data if str(item).strip()}
        return set()

    points: set[str] = set()
    for line in file_path.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            points.add(item.lower())
    return points


def _open_csv_dict_reader(csv_path: str) -> tuple[object, csv.DictReader, list[str]]:
    """Open CSV with encoding fallbacks used by real OC exports."""
    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
    last_error: UnicodeDecodeError | None = None

    for encoding in encodings:
        file = open(csv_path, "r", encoding=encoding, newline="")
        try:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames or []
            return file, reader, fieldnames
        except UnicodeDecodeError as exc:
            file.close()
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise UnicodeDecodeError("utf-8", b"", 0, 1, "Unable to decode CSV with supported encodings")


def _resolve_csv_column(fieldnames: list[str], requested: str, aliases: tuple[str, ...]) -> str:
    lookup = {name.strip().lower(): name for name in fieldnames}
    requested_key = requested.strip().lower()
    if requested_key in lookup:
        return lookup[requested_key]

    for alias in aliases:
        alias_key = alias.strip().lower()
        if alias_key in lookup:
            return lookup[alias_key]

    return ""


# -----------------------------------------------------------------------------
# CSV customer selection helpers
# -----------------------------------------------------------------------------
# Select unique customers whose records fall inside the configured time window.
def _customers_from_csv(
    csv_path: str,
    timestamp_column: str,
    customer_column: str,
    window_hours: int,
    max_customers: int,
) -> list[tuple[str, str]]:
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=max(1, window_hours))
    customers: list[tuple[str, str]] = []
    seen: set[str] = set()

    file, reader, fieldnames = _open_csv_dict_reader(csv_path)
    try:

        effective_timestamp_col = timestamp_column
        effective_customer_col = customer_column

        # Fallbacks for mock OC CSV export headers.
        resolved_timestamp_col = _resolve_csv_column(
            fieldnames,
            effective_timestamp_col,
            (
                "ED Service Last Status (Last Seen)",
                "ED Service Last Status Change (datetime)",
                "Last Seen",
            ),
        )
        if not resolved_timestamp_col:
            raise KeyError(f"Missing column: {timestamp_column}")
        effective_timestamp_col = resolved_timestamp_col

        resolved_customer_col = _resolve_csv_column(
            fieldnames,
            effective_customer_col,
            ("Customer Name",),
        )
        if not resolved_customer_col:
            raise KeyError(f"Missing column: {customer_column}")
        effective_customer_col = resolved_customer_col

        for row in reader:
            customer = str(row.get(effective_customer_col, "")).strip()
            timestamp_raw = str(row.get(effective_timestamp_col, "")).strip()
            if not customer or customer in seen:
                continue

            parsed = _parse_time(timestamp_raw)
            if not parsed:
                continue

            if start_time <= parsed <= end_time:
                customers.append((customer, parsed.isoformat(timespec="seconds")))
                seen.add(customer)
                if len(customers) >= max_customers:
                    break
    finally:
        file.close()

    return customers


# Fallback selector used when strict time-window filtering returns nothing.
def _customers_from_csv_no_window(
    csv_path: str,
    timestamp_column: str,
    customer_column: str,
    max_customers: int,
) -> list[tuple[str, str]]:
    customers: list[tuple[str, str]] = []
    seen: set[str] = set()

    file, reader, fieldnames = _open_csv_dict_reader(csv_path)
    try:

        effective_timestamp_col = timestamp_column
        effective_customer_col = customer_column

        resolved_timestamp_col = _resolve_csv_column(
            fieldnames,
            effective_timestamp_col,
            (
                "ED Service Last Status (Last Seen)",
                "ED Service Last Status Change (datetime)",
                "Last Seen",
            ),
        )
        if resolved_timestamp_col:
            effective_timestamp_col = resolved_timestamp_col

        resolved_customer_col = _resolve_csv_column(
            fieldnames,
            effective_customer_col,
            ("Customer Name",),
        )
        if not resolved_customer_col:
            raise KeyError(f"Missing column: {customer_column}")
        effective_customer_col = resolved_customer_col

        for row in reader:
            customer = str(row.get(effective_customer_col, "")).strip()
            timestamp_raw = str(row.get(effective_timestamp_col, "")).strip()
            if not customer or customer in seen:
                continue

            parsed = _parse_time(timestamp_raw)
            timestamp_iso = parsed.isoformat(timespec="seconds") if parsed else ""

            customers.append((customer, timestamp_iso))
            seen.add(customer)
            if len(customers) >= max_customers:
                break
    finally:
        file.close()

    return customers


def _select_customers_for_loop(
    csv_path: str,
    timestamp_column: str,
    customer_column: str,
    window_hours: int,
    max_customers: int,
    no_window_fraction: float,
) -> tuple[list[tuple[str, str]], str]:
    window_customers = _customers_from_csv(
        csv_path=csv_path,
        timestamp_column=timestamp_column,
        customer_column=customer_column,
        window_hours=window_hours,
        max_customers=max_customers,
    )

    fraction = max(0.0, min(1.0, float(no_window_fraction)))
    if fraction <= 0.0:
        if window_customers:
            return window_customers, "strict_window_only"
        fallback_customers = _customers_from_csv_no_window(
            csv_path=csv_path,
            timestamp_column=timestamp_column,
            customer_column=customer_column,
            max_customers=max_customers,
        )
        return fallback_customers, "fallback_no_window_all"

    bypass_target = int(round(max_customers * fraction))
    bypass_target = max(0, min(max_customers, bypass_target))
    window_target = max(0, max_customers - bypass_target)

    no_window_customers = _customers_from_csv_no_window(
        csv_path=csv_path,
        timestamp_column=timestamp_column,
        customer_column=customer_column,
        max_customers=max_customers,
    )

    selected: list[tuple[str, str]] = []
    seen_names: set[str] = set()

    # Keep a window-constrained segment first.
    for item in window_customers:
        name = item[0]
        if name in seen_names:
            continue
        selected.append(item)
        seen_names.add(name)
        if len(selected) >= window_target:
            break

    strict_names = {name for name, _ in window_customers}
    bypass_added = 0

    # Prefer bypass customers that are outside the strict 24-hour set.
    for item in no_window_customers:
        name = item[0]
        if name in seen_names or name in strict_names:
            continue
        selected.append(item)
        seen_names.add(name)
        bypass_added += 1
        if bypass_added >= bypass_target or len(selected) >= max_customers:
            break

    mode = (
        f"mixed_window_and_no_window(window={len(window_customers)}, "
        f"window_target={window_target}, target_bypass={bypass_target}, selected={len(selected)})"
    )
    return selected, mode


# -----------------------------------------------------------------------------
# Playwright interaction helpers
# -----------------------------------------------------------------------------
# Click by matching visible text with several selector strategies.
async def _click_text(page, text: str, timeout_ms: int) -> bool:
    selectors = [
        f"text={text}",
        f"a:has-text('{text}')",
        f"button:has-text('{text}')",
        f"[role='button']:has-text('{text}')",
        f"[aria-label*='{text}']",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            await locator.click(timeout=timeout_ms)
            return True
        except Exception:
            continue
    return False


# Click first available selector from a candidate list.
async def _click_any(page, selectors: list[str], timeout_ms: int) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            await locator.click(timeout=timeout_ms)
            return True
        except Exception:
            continue
    return False


# Fill common search boxes and submit with Enter.
async def _fill_search(page, query: str, timeout_ms: int) -> bool:
    selectors = [
        "input[type='search']",
        "input[placeholder*='Search']",
        "input[placeholder*='search']",
        "input[aria-label*='Search']",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            await locator.fill(query, timeout=timeout_ms)
            await page.keyboard.press("Enter")
            return True
        except Exception:
            continue
    return False


# Open a filter and apply one or more option labels.
async def _apply_filter(page, filter_name: str, option_labels: Iterable[str], timeout_ms: int) -> bool:
    if not await _click_text(page, filter_name, timeout_ms):
        return False

    applied_any = False
    for option in option_labels:
        if await _click_text(page, option, timeout_ms):
            applied_any = True
    return applied_any


# -----------------------------------------------------------------------------
# Text extraction helpers
# -----------------------------------------------------------------------------
def _extract_datapoints(text: str) -> list[str]:
    # Best-effort parse for datapoint-like tokens across different OC layouts.
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_./:-]{2,}", text or "")
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        lowered = token.lower()
        if "datapoint" in lowered or "tag" in lowered or "sensor" in lowered:
            key = token.strip()
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return out


def _extract_adapter_id(text: str) -> str:
    patterns = [
        r"Adapter\s*ID\s*[:#]?\s*([A-Za-z0-9_-]{3,})",
        r"adapter_id\s*[:=]\s*([A-Za-z0-9_-]{3,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.IGNORECASE)
        if match:
            return match.group(1)

    # UUID fallback used by mock OC details panel.
    uuid_match = re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        text or "",
        flags=re.IGNORECASE,
    )
    if uuid_match:
        return uuid_match.group(0)
    return ""


def _extract_ip(text: str) -> str:
    match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text or "")
    return match.group(0) if match else ""


def _find_latest_download(download_dir: str, glob_expr: str) -> str:
    directory = Path(download_dir)
    candidates = list(directory.glob(glob_expr))
    if not candidates:
        raise FileNotFoundError(f"No downloaded files found in {download_dir} matching {glob_expr}")
    latest = max(candidates, key=lambda item: item.stat().st_mtime)
    return str(latest)


# -----------------------------------------------------------------------------
# Environment and decision helpers
# -----------------------------------------------------------------------------
def _env_flag_enabled(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_start_step() -> int:
    step_1_enabled = _env_flag_enabled("STEP_1")
    step_2_enabled = _env_flag_enabled("STEP_2")

    if step_1_enabled and step_2_enabled:
        raise ValueError("Invalid start configuration: only one of STEP_1 or STEP_2 can be true")

    if step_2_enabled:
        return 2
    return 1


# LLM-based datapoint decision used in eligibility checks.
def _llm_datapoint_match(
    config: MonitorConfig,
    error_datapoints: list[str],
    reference_datapoints: set[str],
) -> tuple[bool, list[str], str]:
    logger = logging.getLogger("operation_console_monitor")

    if not reference_datapoints:
        return True, [], "No reference datapoints configured"

    if not error_datapoints:
        return False, [], "No error datapoints found under error state"

    schema = {
        "type": "object",
        "properties": {
            "is_match": {"type": "boolean"},
            "matched_error_datapoints": {
                "type": "array",
                "items": {"type": "string"},
            },
            "reason": {"type": "string"},
        },
        "required": ["is_match", "matched_error_datapoints", "reason"],
    }

    ref_sorted = sorted(reference_datapoints)
    prompt = (
        "Compare operation-console datapoints. "
        "Return JSON only, matching schema. "
        "Set is_match=true only when error datapoints belong to the provided reference list.\n\n"
        "Reference datapoints:\n"
        + "\n".join(f"- {item}" for item in ref_sorted)
        + "\n\nError-state datapoints:\n"
        + "\n".join(f"- {item}" for item in error_datapoints)
    )

    payload = {
        "model": config.ollama.model,
        "messages": [
            {"role": "system", "content": "You are a strict JSON generator."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": schema,
        "options": {"temperature": 0},
    }

    url = f"{config.ollama.base_url.rstrip('/')}/api/chat"
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    logger.info(
        "Ollama datapoint-match request started | model=%s | reference_count=%s | error_count=%s",
        config.ollama.model,
        len(reference_datapoints),
        len(error_datapoints),
    )
    started = perf_counter()
    try:
        with request.urlopen(req, timeout=config.ollama.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.exception("Ollama datapoint-match request failed | model=%s | error=%s", config.ollama.model, exc)
        raise

    elapsed_ms = int((perf_counter() - started) * 1000)
    logger.info(
        "Ollama datapoint-match response received | model=%s | elapsed_ms=%s | done=%s",
        config.ollama.model,
        elapsed_ms,
        bool(body.get("done", False)),
    )

    content = body.get("message", {}).get("content", "{}")
    parsed = json.loads(content) if isinstance(content, str) else {}

    matched_raw = parsed.get("matched_error_datapoints", [])
    if not isinstance(matched_raw, list):
        matched_raw = []

    error_lookup = {item.strip().lower(): item.strip() for item in error_datapoints if item.strip()}
    matched = [
        error_lookup.get(str(item).strip().lower(), str(item).strip())
        for item in matched_raw
        if str(item).strip()
    ]

    # Keep stable ordering and unique values.
    seen: set[str] = set()
    matched_ordered: list[str] = []
    for item in matched:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        matched_ordered.append(item)

    is_match = bool(parsed.get("is_match", False))
    reason = str(parsed.get("reason", "Ollama datapoint decision completed")).strip()
    logger.info(
        "Ollama datapoint-match decision | is_match=%s | matched_count=%s",
        is_match,
        len(matched_ordered),
    )
    return is_match, matched_ordered, reason


# -----------------------------------------------------------------------------
# Main OC workflow execution
# -----------------------------------------------------------------------------
# Runs phase A/B/C automation and returns a serializable workflow report.
async def _run_workflow_async(config: MonitorConfig, run_id: str, timestamp: str) -> dict:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        raise RuntimeError(
            "Playwright is required. Install dependencies and run: python -m playwright install chromium"
        ) from exc

    logger = logging.getLogger("operation_console_monitor")
    timeout_ms = max(1, config.oc_workflow.step_timeout_seconds) * 1000
    ref_points = _load_reference_datapoints(config.oc_workflow.datapoints_reference_file)
    start_step = _resolve_start_step()
    phase_logs: list[str] = []
    captured_errors: list[str] = []

    def log_phase(message: str) -> None:
        line = f"[PHASE] {message}"
        phase_logs.append(line)
        logger.info(line)

    def log_step(message: str) -> None:
        line = f"[STEP] {message}"
        phase_logs.append(line)
        logger.info(line)

    def log_error(message: str) -> None:
        line = f"[ERROR] {message}"
        captured_errors.append(line)
        phase_logs.append(line)
        logger.error(line)

    # Step 1: Open browser context and load operation console URL.
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=config.skyvern.headless,
            args=config.skyvern.extra_chromium_args,
        )
        context = await browser.new_context(
            accept_downloads=True,
            viewport={
                "width": config.skyvern.viewport_width,
                "height": config.skyvern.viewport_height,
            },
        )
        page = await context.new_page()

        await page.goto(
            config.operation_console_url,
            wait_until="load",
            timeout=config.skyvern.navigation_timeout_seconds * 1000,
        )

        log_phase(f"Workflow start configured with STEP_{start_step}=true")

        # Step 2: Sign in path.
        log_step("Executing Step 2: SSO sign in")
        await _click_any(
            page,
            [
                "#coprote-sso",
                "button:has-text('Sign in with Coprote ID (SSO)')",
                "button:has-text('Sign in')",
                "button:has-text('Sign In')",
                "text=SSO",
            ],
            timeout_ms,
        )
        try:
            await page.wait_for_url("**/dashboard.html", timeout=max(1, config.oc_workflow.login_wait_seconds) * 1000)
        except Exception:
            # Fallback: dashboard shell marker used by mock and some OC layouts.
            try:
                await page.wait_for_selector("#monitoring-toggle", timeout=max(1, config.oc_workflow.login_wait_seconds) * 1000)
            except Exception:
                pass

        downloaded_csv = ""
        customers: list[tuple[str, str]] = []

        # Phase A: Optional login/filter/download path when starting at STEP_1.
        if start_step == 1:
            log_phase("Phase A started: login + monitoring extraction")

            # Step 3 + 4: Monitoring and filters.
            log_step("Executing Step 3-4: open Monitoring and apply required filters")
            await _click_any(page, ["#monitoring-toggle", "text=Monitoring", "text=Montoring"], timeout_ms)
            await page.wait_for_timeout(300)

            # Mock-specific deterministic filters first.
            try:
                await page.select_option("#filter-ed-status", value="OK", timeout=timeout_ms)
            except Exception:
                _ = await _apply_filter(page, "ED Status", ["OK"], timeout_ms)

            # Mock has Major/Minor/Ignore; Critical may not exist there.
            try:
                await page.select_option("#filter-ed-service-status", value="Major", timeout=timeout_ms)
            except Exception:
                _ = await _apply_filter(page, "ED Service Status", ["Major", "Critical"], timeout_ms)

            try:
                await page.select_option("#filter-ed-condition", value="Subscription and Smart COM", timeout=timeout_ms)
            except Exception:
                _ = await _apply_filter(page, "ED Condition", ["Subscription", "Smart COM"], timeout_ms)

            # Step 5 + 6: Download CSV.
            log_step("Executing Step 5-6: download Monitoring CSV")
            download_success = False
            try:
                async with page.expect_download(timeout=max(timeout_ms, 30000)) as dl_info:
                    if not await _click_any(
                        page,
                        [
                            "#download-visible-csv",
                            "button[aria-label*='Download']",
                            "[title*='Download']",
                            "text=Download",
                        ],
                        timeout_ms,
                    ):
                        raise RuntimeError("Download button not found")
                download = await dl_info.value
                download_target = Path(config.paths.downloads_dir) / f"{run_id}-{download.suggested_filename}"
                await download.save_as(str(download_target))
                download_success = True
            except Exception:
                pass

            if not download_success:
                # Fallback selectors for icon-only buttons.
                for selector in [
                    "button[aria-label*='Download']",
                    "[title*='Download']",
                    "[data-testid*='download']",
                ]:
                    try:
                        async with page.expect_download(timeout=max(timeout_ms, 30000)) as dl_info:
                            await page.locator(selector).first.click(timeout=timeout_ms)
                        download = await dl_info.value
                        download_target = Path(config.paths.downloads_dir) / f"{run_id}-{download.suggested_filename}"
                        await download.save_as(str(download_target))
                        download_success = True
                        break
                    except Exception:
                        continue

            if not download_success:
                log_error("Failed to download monitoring CSV from OC")
                raise RuntimeError("Failed to download monitoring CSV from OC")

            downloaded_csv = _find_latest_download(
                config.paths.downloads_dir,
                config.oc_workflow.downloaded_csv_glob,
            )
            log_step(f"Downloaded CSV detected: {downloaded_csv}")

            log_step("Executing Step 7-8: filter customers in 24-hour window and prepare loop list")
            customers, selection_mode = _select_customers_for_loop(
                csv_path=downloaded_csv,
                timestamp_column=config.oc_workflow.timestamp_column,
                customer_column=config.oc_workflow.customer_column,
                window_hours=config.oc_workflow.window_hours,
                max_customers=config.oc_workflow.max_customers_per_run,
                no_window_fraction=config.oc_workflow.no_window_fraction,
            )
            log_step(f"Customer selection mode: {selection_mode}")

            if not customers:
                warning_line = "No customers selected from CSV after applying selection rules."
                phase_logs.append(f"[WARN] {warning_line}")
                logger.warning("[WARN] %s", warning_line)

            log_phase(f"Phase A completed: selected {len(customers)} customer(s) for investigation loop")
        else:
            # Phase A skip path: consume existing CSV and continue with investigation loop.
            log_phase("Phase A skipped: STEP_2=true, using an already downloaded CSV")
            downloaded_csv = _find_latest_download(
                config.paths.downloads_dir,
                config.oc_workflow.downloaded_csv_glob,
            )
            log_step(f"Using provided CSV for Step 2 start: {downloaded_csv}")
            log_step("Executing Step 7-8: filter customers in 24-hour window and prepare loop list")
            customers, selection_mode = _select_customers_for_loop(
                csv_path=downloaded_csv,
                timestamp_column=config.oc_workflow.timestamp_column,
                customer_column=config.oc_workflow.customer_column,
                window_hours=config.oc_workflow.window_hours,
                max_customers=config.oc_workflow.max_customers_per_run,
                no_window_fraction=config.oc_workflow.no_window_fraction,
            )
            log_step(f"Customer selection mode: {selection_mode}")

            if not customers:
                warning_line = "No customers selected from CSV after applying selection rules."
                phase_logs.append(f"[WARN] {warning_line}")
                logger.warning("[WARN] %s", warning_line)

            log_phase(f"Phase B entry: selected {len(customers)} customer(s) for investigation loop")

        # Phase B/C: Per-customer investigation and outcome classification.
        results: list[CustomerInvestigationResult] = []
        for index, (customer_name, customer_ts) in enumerate(customers, start=1):
            steps: list[StepResult] = []
            status = "investigated"
            outcome = ""
            adapter_id = ""
            machine_ip = ""
            matched_datapoints: list[str] = []
            error_datapoints: list[str] = []
            account_monitoring_evidence_screenshot = ""
            account_monitoring_service_status_evidence_screenshot = ""
            account_monitoring_das_service_status_evidence_screenshot = ""
            account_monitoring_service_status_source_id = ""
            account_monitoring_das_service_status_source_id = ""
            das_validation_evidence_screenshot = ""
            das_validation_all_rows_evidence_screenshot = ""
            das_validation_observed_source_ids: list[str] = []
            das_validation_source_id_match: bool | None = None

            shot_prefix = Path(config.paths.screenshots_dir) / f"{run_id}-{customer_name.replace(' ', '-')[:40]}"

            log_phase(f"Phase B started: customer loop {index}/{len(customers)} for '{customer_name}'")

            try:
                log_step("Executing Step 9-10: open Monitoring account view and search customer")
                await _click_any(page, ["#monitoring-toggle", "text=Monitoring", "text=Montoring"], timeout_ms)
                await page.wait_for_timeout(200)
                await _click_any(page, ["#account-monitoring-submenu-link", "text=Account Monitoring"], timeout_ms)
                await page.wait_for_timeout(300)

                searched = False
                try:
                    await page.fill("#account-monitoring-search", customer_name, timeout=timeout_ms)
                    searched = True
                except Exception:
                    searched = await _fill_search(page, customer_name, timeout_ms)

                if searched:
                    steps.append(StepResult(name="search_customer", status="ok", details=customer_name))
                else:
                    steps.append(StepResult(name="search_customer", status="failed", details="Search input not found"))
                    status = "failed"

                await page.wait_for_timeout(400)
                await page.screenshot(path=str(shot_prefix) + "-details.png", full_page=True)

                # Evidence capture: explicitly capture Service Status and DAS Service Status major rows.
                account_monitoring_evidence_path = str(shot_prefix) + "-account-monitoring-evidence.png"
                try:
                    await _click_any(page, ["#account-tab-service", "text=Service Status"], timeout_ms)
                    await page.wait_for_timeout(200)

                    async def _capture_account_row(label: str, suffix: str) -> tuple[str, str]:
                        rows = page.locator("#account-status-body tr")
                        row_count = await rows.count()
                        for row_index in range(row_count):
                            row = rows.nth(row_index)
                            try:
                                row_label = (await row.locator("td").first.inner_text(timeout=timeout_ms)).strip().lower()
                            except Exception:
                                continue
                            if row_label != label.lower():
                                continue
                            try:
                                await row.hover(timeout=timeout_ms)
                            except Exception:
                                await row.click(timeout=timeout_ms)
                            await page.wait_for_timeout(200)
                            output_path = str(shot_prefix) + f"-account-monitoring-{suffix}-evidence.png"
                            await page.screenshot(path=output_path, full_page=True)
                            details_text = ""
                            try:
                                details_text = await page.locator("#account-error-details").inner_text(timeout=timeout_ms)
                            except Exception:
                                details_text = ""
                            source_id = _extract_adapter_id(details_text)
                            return output_path, source_id
                        return "", ""

                    (
                        account_monitoring_service_status_evidence_screenshot,
                        account_monitoring_service_status_source_id,
                    ) = await _capture_account_row(
                        "Service status",
                        "service-status",
                    )
                    (
                        account_monitoring_das_service_status_evidence_screenshot,
                        account_monitoring_das_service_status_source_id,
                    ) = await _capture_account_row(
                        "DAS service status",
                        "das-service-status",
                    )

                    account_monitoring_evidence_screenshot = (
                        account_monitoring_service_status_evidence_screenshot
                        or account_monitoring_das_service_status_evidence_screenshot
                    )

                    if not account_monitoring_evidence_screenshot:
                        await page.screenshot(path=account_monitoring_evidence_path, full_page=True)
                        account_monitoring_evidence_screenshot = account_monitoring_evidence_path

                    await page.wait_for_timeout(200)
                    steps.append(
                        StepResult(
                            name="capture_account_monitoring_evidence",
                            status=(
                                "ok"
                                if account_monitoring_service_status_evidence_screenshot
                                and account_monitoring_das_service_status_evidence_screenshot
                                else "partial"
                            ),
                            details=(
                                "Captured Service Status and DAS Service Status evidence"
                                if account_monitoring_service_status_evidence_screenshot
                                and account_monitoring_das_service_status_evidence_screenshot
                                else "Captured partial Account Monitoring evidence"
                            ),
                            screenshot=account_monitoring_evidence_screenshot,
                        )
                    )
                except Exception as evidence_exc:
                    steps.append(
                        StepResult(
                            name="capture_account_monitoring_evidence",
                            status="failed",
                            details=str(evidence_exc),
                        )
                    )

                log_step("Executing Step 11: validate component status is Major Problem")
                major_problem_detected = False
                component_checks: list[str] = []
                try:
                    rows = page.locator("#account-status-body tr")
                    row_count = await rows.count()
                    target_labels = {"service status", "das service status", "component status"}

                    for row_index in range(row_count):
                        row = rows.nth(row_index)
                        try:
                            label_text = (await row.locator("td").first.inner_text(timeout=timeout_ms)).strip().lower()
                        except Exception:
                            continue

                        if label_text not in target_labels:
                            continue

                        row_text = (await row.inner_text(timeout=timeout_ms)).strip()
                        is_major_problem = bool(re.search(r"\bmajor\s*problem\b", row_text, flags=re.IGNORECASE))
                        major_problem_detected = major_problem_detected or is_major_problem
                        component_checks.append(
                            f"{label_text}={'major_problem' if is_major_problem else 'not_major_problem'}"
                        )
                except Exception as component_exc:
                    component_checks.append(f"component_status_parse_failed={component_exc}")

                if not major_problem_detected:
                    status = "skipped"
                    outcome = "Skipped - Not Eligible (Component status not Major Problem)"
                    steps.append(
                        StepResult(
                            name="validate_component_status",
                            status="failed",
                            details=(
                                "; ".join(component_checks)
                                if component_checks
                                else "No component/service status row with Major Problem"
                            ),
                        )
                    )
                    results.append(
                        CustomerInvestigationResult(
                            customer_name=customer_name,
                            timestamp_iso=customer_ts,
                            status=status,
                            adapter_id=adapter_id,
                            machine_ip=machine_ip,
                            matched_datapoints=matched_datapoints,
                            error_datapoints=error_datapoints,
                            evidence_account_monitoring_screenshot=account_monitoring_evidence_screenshot,
                            evidence_account_monitoring_service_status_screenshot=account_monitoring_service_status_evidence_screenshot,
                            evidence_account_monitoring_das_service_status_screenshot=account_monitoring_das_service_status_evidence_screenshot,
                            evidence_das_validation_screenshot=das_validation_evidence_screenshot,
                            evidence_das_validation_all_rows_screenshot=das_validation_all_rows_evidence_screenshot,
                            evidence_das_validation_observed_source_ids=das_validation_observed_source_ids,
                            evidence_das_validation_source_id_match=das_validation_source_id_match,
                            outcome=outcome,
                            steps=steps,
                        )
                    )
                    log_phase(f"Phase B completed for '{customer_name}' with status: {status}")
                    continue

                steps.append(
                    StepResult(
                        name="validate_component_status",
                        status="ok",
                        details="Component status shows Major Problem; proceeding to Readkit",
                    )
                )

                log_step("Executing Step 12-15: validate Readkit status, service status, adapter ID, datapoints")
                _ = await page.inner_text("body")
                # Mock readkit tab exposes KOP/RK/ED style status rows.
                await _click_any(page, ["#account-tab-readkit", "text=Readkit Status"], timeout_ms)
                await page.wait_for_timeout(250)
                # Only inspect Readkit status rows; global page text contains static
                # labels like "Error Details" that can create false negatives.
                try:
                    readkit_scope = page.locator("#readkit-status-body").first
                    readkit_text = await readkit_scope.inner_text(timeout=timeout_ms)
                except Exception:
                    # Fallback keeps behavior predictable if selectors are unavailable.
                    readkit_text = await page.inner_text("body")

                target_labels = ("kop", "rk", "ed")
                non_ok_pattern = re.compile(r"\b(error|warn|warning|critical|major|minor|failed|down|unknown)\b", re.IGNORECASE)
                ok_pattern = re.compile(r"\bok\b", re.IGNORECASE)

                # Track per-label state: ok | non_ok | unknown.
                label_states: dict[str, str] = {}
                for label in target_labels:
                    label_states[label] = "unknown"

                # Prefer structured table parsing so label/status in separate cells works.
                parsed_table_rows = False
                try:
                    rows = page.locator("#readkit-status-body tr")
                    row_count = await rows.count()
                    for row_index in range(row_count):
                        row = rows.nth(row_index)
                        cells = row.locator("td")
                        if await cells.count() == 0:
                            continue

                        label_text = (await cells.nth(0).inner_text(timeout=timeout_ms)).strip().lower()
                        row_text = (await row.inner_text(timeout=timeout_ms)).strip()
                        status_text = row_text
                        status_html = (await row.inner_html(timeout=timeout_ms)).lower()
                        if await cells.count() > 1:
                            status_text = (await cells.nth(1).inner_text(timeout=timeout_ms)).strip()
                            status_html = (await cells.nth(1).inner_html(timeout=timeout_ms)).lower()

                        for label in target_labels:
                            if not re.search(rf"\b{label}\b", label_text):
                                continue

                            parsed_table_rows = True
                            has_non_ok = bool(non_ok_pattern.search(status_text)) or (
                                "status-badge warn" in status_html
                                or "status-badge error" in status_html
                                or "badge warn" in status_html
                                or "badge error" in status_html
                            )
                            has_ok = (
                                bool(ok_pattern.search(status_text)) and not has_non_ok
                            ) or ("status-badge ok" in status_html or "badge ok" in status_html)

                            if has_ok:
                                label_states[label] = "ok"
                            elif has_non_ok:
                                label_states[label] = "non_ok"
                except Exception:
                    parsed_table_rows = False

                # Fallback to line parsing when table markup is unavailable.
                if not parsed_table_rows:
                    readkit_lines = [line.strip() for line in readkit_text.splitlines() if line.strip()]
                    for line in readkit_lines:
                        lowered = line.lower()
                        for label in target_labels:
                            if not re.search(rf"\b{label}\b", lowered):
                                continue
                            has_non_ok = bool(non_ok_pattern.search(line))
                            has_ok = bool(ok_pattern.search(line)) and not has_non_ok
                            if has_ok:
                                label_states[label] = "ok"
                            elif has_non_ok:
                                label_states[label] = "non_ok"

                all_labels_ok = all(label_states.get(label) == "ok" for label in target_labels)
                any_label_non_ok = any(label_states.get(label) == "non_ok" for label in target_labels)

                if all_labels_ok:
                    status_ok = True
                elif any_label_non_ok:
                    status_ok = False
                else:
                    # Ambiguous/partial status: continue unless explicit non-ok text exists.
                    status_ok = not bool(non_ok_pattern.search(readkit_text))

                await _click_any(page, ["#account-tab-service", "text=Service Status"], timeout_ms)
                if not status_ok:
                    status = "skipped"
                    outcome = "Skipped - Not Eligible (Status not OK)"
                    details = (
                        f"KOP/RK/ED status not explicitly OK; checks={label_states}"
                    )
                    steps.append(StepResult(name="validate_ed_status", status="failed", details=details))
                    results.append(
                        CustomerInvestigationResult(
                            customer_name=customer_name,
                            timestamp_iso=customer_ts,
                            status=status,
                            adapter_id=adapter_id,
                            machine_ip=machine_ip,
                            matched_datapoints=matched_datapoints,
                            error_datapoints=error_datapoints,
                            evidence_account_monitoring_screenshot=account_monitoring_evidence_screenshot,
                            evidence_account_monitoring_service_status_screenshot=account_monitoring_service_status_evidence_screenshot,
                            evidence_account_monitoring_das_service_status_screenshot=account_monitoring_das_service_status_evidence_screenshot,
                            evidence_das_validation_screenshot=das_validation_evidence_screenshot,
                            evidence_das_validation_all_rows_screenshot=das_validation_all_rows_evidence_screenshot,
                            evidence_das_validation_observed_source_ids=das_validation_observed_source_ids,
                            evidence_das_validation_source_id_match=das_validation_source_id_match,
                            outcome=outcome,
                            steps=steps,
                        )
                    )
                    log_phase(f"Phase B completed for '{customer_name}' with status: {status}")
                    continue
                steps.append(StepResult(name="validate_ed_status", status="ok", details="Proceed"))

                await page.wait_for_timeout(350)
                body_after_service = await page.inner_text("body")
                adapter_id = (
                    account_monitoring_service_status_source_id
                    or account_monitoring_das_service_status_source_id
                    or _extract_adapter_id(body_after_service)
                )
                datapoints = _extract_datapoints(body_after_service)
                steps.append(
                    StepResult(
                        name="capture_adapter_and_datapoints",
                        status="ok" if adapter_id else "partial",
                        details=(
                            f"adapter_id={adapter_id or 'not_found'}, datapoints={len(datapoints)}, "
                            f"service_row_source_id={account_monitoring_service_status_source_id or 'n/a'}, "
                            f"das_service_row_source_id={account_monitoring_das_service_status_source_id or 'n/a'}"
                        ),
                    )
                )

                log_step("Executing Step 15-19: open DAS Validation and filter error state")
                await _click_any(page, ["#monitoring-toggle", "text=Monitoring", "text=Montoring"], timeout_ms)
                await _click_any(page, ["#das-validation-link", "text=DAS Validation"], timeout_ms)
                await page.wait_for_timeout(350)

                if adapter_id:
                    try:
                        await page.fill("#das-adapters-search", adapter_id, timeout=timeout_ms)
                    except Exception:
                        _ = await _fill_search(page, adapter_id, timeout_ms)

                await page.wait_for_timeout(300)
                # Open adapter details for matching adapter row whenever available.
                opened_details = False
                if adapter_id:
                    opened_details = await _click_any(
                        page,
                        [
                            f"#das-adapters-body tr:has-text('{adapter_id}') .das-row-open",
                            f"tr:has-text('{adapter_id}') .das-row-open",
                        ],
                        timeout_ms,
                    )
                if not opened_details:
                    await _click_any(page, [".das-row-open", "text=i"], timeout_ms)
                await page.wait_for_timeout(250)

                das_validation_all_rows_evidence_path = str(shot_prefix) + "-das-validation-all-rows-evidence.png"
                try:
                    await page.screenshot(path=das_validation_all_rows_evidence_path, full_page=True)
                    das_validation_all_rows_evidence_screenshot = das_validation_all_rows_evidence_path
                    steps.append(
                        StepResult(
                            name="capture_das_validation_all_rows_evidence",
                            status="ok",
                            details="Captured DAS validation with all rows before filtering",
                            screenshot=das_validation_all_rows_evidence_path,
                        )
                    )
                except Exception as evidence_exc:
                    steps.append(
                        StepResult(
                            name="capture_das_validation_all_rows_evidence",
                            status="failed",
                            details=str(evidence_exc),
                        )
                    )

                requested_state = str(config.oc_workflow.das_state_filter).strip().lower() or "faulted"
                state_candidates: list[str] = []
                for candidate in (requested_state, "faulted", "error"):
                    if candidate and candidate not in state_candidates:
                        state_candidates.append(candidate)

                state_applied = False
                for candidate in state_candidates:
                    try:
                        await page.select_option("#das-detail-state-filter", value=candidate, timeout=timeout_ms)
                        state_applied = True
                        break
                    except Exception:
                        continue

                if not state_applied:
                    await _click_text(page, "STATE", timeout_ms)
                    for candidate in state_candidates:
                        if await _click_text(page, candidate, timeout_ms):
                            state_applied = True
                            break
                await page.wait_for_timeout(300)

                das_text = await page.inner_text("body")
                # Prefer table tags from DAS detail table in mock.
                try:
                    tag_cells = await page.locator("#das-read-values-body tr td.tag-text").all_inner_texts()
                    error_datapoints = [item.strip() for item in tag_cells if item.strip()]
                except Exception:
                    error_datapoints = _extract_datapoints(das_text)

                try:
                    source_cells = await page.locator("#das-read-values-body tr td:nth-child(3)").all_inner_texts()
                    source_ids = sorted({str(item).strip() for item in source_cells if str(item).strip()})
                    das_validation_observed_source_ids = source_ids
                    if adapter_id:
                        das_validation_source_id_match = adapter_id.lower() in {item.lower() for item in source_ids}
                    steps.append(
                        StepResult(
                            name="validate_das_source_id_match",
                            status=(
                                "ok"
                                if (das_validation_source_id_match is True or not adapter_id)
                                else "failed"
                            ),
                            details=(
                                f"expected={adapter_id or 'n/a'}, observed={','.join(source_ids) or 'none'}"
                            ),
                        )
                    )
                except Exception as source_id_exc:
                    steps.append(
                        StepResult(
                            name="validate_das_source_id_match",
                            status="failed",
                            details=str(source_id_exc),
                        )
                    )

                das_validation_evidence_path = str(shot_prefix) + "-das-validation-evidence.png"
                try:
                    await page.wait_for_timeout(200)
                    await page.screenshot(path=das_validation_evidence_path, full_page=True)
                    das_validation_evidence_screenshot = das_validation_evidence_path
                    steps.append(
                        StepResult(
                            name="capture_das_validation_evidence",
                            status="ok",
                            details="Captured DAS validation endpoints/datapoints evidence",
                            screenshot=das_validation_evidence_path,
                        )
                    )
                except Exception as evidence_exc:
                    steps.append(
                        StepResult(
                            name="capture_das_validation_evidence",
                            status="failed",
                            details=str(evidence_exc),
                        )
                    )

                if ref_points:
                    log_step("Executing LLM validation gate: compare error datapoints with reference list")
                    try:
                        is_match, matched_datapoints, llm_reason = _llm_datapoint_match(
                            config=config,
                            error_datapoints=error_datapoints,
                            reference_datapoints=ref_points,
                        )
                    except Exception as llm_exc:
                        # Fallback preserves workflow continuity if local Ollama is temporarily unavailable.
                        matched_datapoints = [point for point in error_datapoints if point.lower() in ref_points]
                        is_match = bool(matched_datapoints)
                        llm_reason = f"Ollama unavailable, used exact-match fallback: {llm_exc}"

                    if not is_match:
                        status = "skipped"
                        outcome = "Skipped - Not Eligible (Datapoint mismatch)"
                        steps.append(
                            StepResult(
                                name="datapoint_match_check",
                                status="failed",
                                details=llm_reason,
                            )
                        )
                        results.append(
                            CustomerInvestigationResult(
                                customer_name=customer_name,
                                timestamp_iso=customer_ts,
                                status=status,
                                adapter_id=adapter_id,
                                machine_ip=machine_ip,
                                matched_datapoints=matched_datapoints,
                                error_datapoints=error_datapoints,
                                evidence_account_monitoring_screenshot=account_monitoring_evidence_screenshot,
                                evidence_account_monitoring_service_status_screenshot=account_monitoring_service_status_evidence_screenshot,
                                evidence_account_monitoring_das_service_status_screenshot=account_monitoring_das_service_status_evidence_screenshot,
                                evidence_das_validation_screenshot=das_validation_evidence_screenshot,
                                evidence_das_validation_all_rows_screenshot=das_validation_all_rows_evidence_screenshot,
                                evidence_das_validation_observed_source_ids=das_validation_observed_source_ids,
                                evidence_das_validation_source_id_match=das_validation_source_id_match,
                                outcome=outcome,
                                steps=steps,
                            )
                        )
                        log_phase(f"Phase B completed for '{customer_name}' with status: {status}")
                        continue
                    steps.append(
                        StepResult(
                            name="datapoint_match_check",
                            status="ok",
                            details=llm_reason,
                        )
                    )
                else:
                    steps.append(
                        StepResult(
                            name="datapoint_match_check",
                            status="ok",
                            details="No reference file configured; LLM gate skipped",
                        )
                    )

                log_phase("Phase C started: connectivity verification and outcome decision")
                log_step("Executing Step 20-25: fetch machine IP and run ping via SSM")
                # Step 21-24: copy IP, ping via SSM.
                machine_ip = _extract_ip(das_text)
                await _click_any(page, ["#monitoring-toggle", "text=Monitoring", "text=Montoring"], timeout_ms)
                await _click_any(page, ["#ssm-link", "text=SSM"], timeout_ms)
                await page.wait_for_timeout(250)
                ping_command = f"ping -c3 {machine_ip}" if machine_ip else "ping -c3 127.0.0.1"
                command_sent = False
                for selector in ["#ssm-command-input", "textarea", "input[placeholder*='command']", "input[type='text']"]:
                    try:
                        locator = page.locator(selector).first
                        if await locator.count() == 0:
                            continue
                        await locator.fill(ping_command, timeout=timeout_ms)
                        command_sent = True
                        break
                    except Exception:
                        continue

                if command_sent:
                    await _click_any(page, ["#ssm-start-command", "text=START COMMAND"], timeout_ms)
                    # Wait for async output completion (mock uses loading indicator).
                    try:
                        await page.wait_for_selector("#ssm-loading[hidden]", timeout=5000)
                    except Exception:
                        await page.wait_for_timeout(1800)

                ssm_text = await page.inner_text("body")
                ping_ok = "0% packet loss" in ssm_text or "bytes from" in ssm_text
                if not ping_ok:
                    status = "failed"
                    outcome = "Host Unreachable - Ping Failed"
                    steps.append(StepResult(name="ping_check", status="failed", details=ping_command))
                    results.append(
                        CustomerInvestigationResult(
                            customer_name=customer_name,
                            timestamp_iso=customer_ts,
                            status=status,
                            adapter_id=adapter_id,
                            machine_ip=machine_ip,
                            matched_datapoints=matched_datapoints,
                            error_datapoints=error_datapoints,
                            evidence_account_monitoring_screenshot=account_monitoring_evidence_screenshot,
                            evidence_account_monitoring_service_status_screenshot=account_monitoring_service_status_evidence_screenshot,
                            evidence_account_monitoring_das_service_status_screenshot=account_monitoring_das_service_status_evidence_screenshot,
                            evidence_das_validation_screenshot=das_validation_evidence_screenshot,
                            evidence_das_validation_all_rows_screenshot=das_validation_all_rows_evidence_screenshot,
                            evidence_das_validation_observed_source_ids=das_validation_observed_source_ids,
                            evidence_das_validation_source_id_match=das_validation_source_id_match,
                            outcome=outcome,
                            steps=steps,
                        )
                    )
                    log_phase(f"Phase C completed for '{customer_name}' with status: {status}")
                    continue

                steps.append(StepResult(name="ping_check", status="ok", details=ping_command))

                log_step("Executing Step 26-28: connectivity check and classify outcome")
                # Step 26-28 connectivity branch.
                await _click_any(page, ["#monitoring-toggle", "text=Monitoring", "text=Montoring"], timeout_ms)
                await _click_any(page, ["#connectivity-check-link", "text=Connectivity Check"], timeout_ms)
                await page.wait_for_timeout(300)
                await _click_any(page, ["#connectivity-check-all", "text=CHECK ALL CONNECTIONS"], timeout_ms)
                await page.wait_for_timeout(300)
                connectivity_text = await page.inner_text("body")
                has_red = "🔺" in connectivity_text or "failed" in connectivity_text.lower()
                if has_red:
                    outcome = "NOC Report - Port Issue"
                else:
                    outcome = "NOC Report - Onsite Issue"
                steps.append(
                    StepResult(
                        name="connectivity_check",
                        status="ok",
                        details=outcome,
                    )
                )

                await page.screenshot(path=str(shot_prefix) + "-final.png", full_page=True)
                results.append(
                    CustomerInvestigationResult(
                        customer_name=customer_name,
                        timestamp_iso=customer_ts,
                        status=status,
                        adapter_id=adapter_id,
                        machine_ip=machine_ip,
                        matched_datapoints=matched_datapoints,
                        error_datapoints=error_datapoints,
                        evidence_account_monitoring_screenshot=account_monitoring_evidence_screenshot,
                        evidence_account_monitoring_service_status_screenshot=account_monitoring_service_status_evidence_screenshot,
                        evidence_account_monitoring_das_service_status_screenshot=account_monitoring_das_service_status_evidence_screenshot,
                        evidence_das_validation_screenshot=das_validation_evidence_screenshot,
                        evidence_das_validation_all_rows_screenshot=das_validation_all_rows_evidence_screenshot,
                        evidence_das_validation_observed_source_ids=das_validation_observed_source_ids,
                        evidence_das_validation_source_id_match=das_validation_source_id_match,
                        outcome=outcome,
                        steps=steps,
                    )
                )
                log_phase(f"Phase C completed for '{customer_name}' with outcome: {outcome}")
                log_phase(f"Phase B completed for '{customer_name}' with status: {status}")

            except Exception as customer_exc:
                err = f"Customer '{customer_name}' failed with exception: {customer_exc}"
                log_error(err)
                steps.append(StepResult(name="customer_loop_exception", status="failed", details=str(customer_exc)))
                results.append(
                    CustomerInvestigationResult(
                        customer_name=customer_name,
                        timestamp_iso=customer_ts,
                        status="failed",
                        adapter_id=adapter_id,
                        machine_ip=machine_ip,
                        matched_datapoints=matched_datapoints,
                        error_datapoints=error_datapoints,
                        evidence_account_monitoring_screenshot=account_monitoring_evidence_screenshot,
                        evidence_account_monitoring_service_status_screenshot=account_monitoring_service_status_evidence_screenshot,
                        evidence_account_monitoring_das_service_status_screenshot=account_monitoring_das_service_status_evidence_screenshot,
                        evidence_das_validation_screenshot=das_validation_evidence_screenshot,
                        evidence_das_validation_all_rows_screenshot=das_validation_all_rows_evidence_screenshot,
                        evidence_das_validation_observed_source_ids=das_validation_observed_source_ids,
                        evidence_das_validation_source_id_match=das_validation_source_id_match,
                        outcome="Execution Error",
                        steps=steps,
                    )
                )

        await context.close()
        await browser.close()
        log_phase("Workflow execution completed, browser context closed")

    # Build final report payload consumed by orchestrator exports.
    report = OCWorkflowReport(
        run_id=run_id,
        timestamp=timestamp,
        console_url=config.operation_console_url,
        downloaded_csv=downloaded_csv,
        window_hours=config.oc_workflow.window_hours,
        customers_in_window=len(customers),
        investigated_customers=len(results),
        results=results,
        phase_logs=phase_logs,
        errors=captured_errors,
    )
    return report.to_dict()


# Synchronous wrapper for CLI and orchestrator callers.
def run_oc_workflow(config: MonitorConfig, run_id: str, timestamp: str) -> dict:
    return asyncio.run(_run_workflow_async(config, run_id, timestamp))
