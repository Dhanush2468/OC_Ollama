from __future__ import annotations

from dataclasses import asdict, dataclass


# -----------------------------------------------------------------------------
# Monitoring report models
# -----------------------------------------------------------------------------
# Single issue item produced by model analysis.
@dataclass
class Finding:
    timestamp: str
    severity: str
    issue: str
    recommendation: str
    evidence: str
    screenshot: str
    details: str = ""
    source_view: str = "main"


@dataclass
class MonitoringReport:
    run_id: str
    timestamp: str
    console_url: str
    page_url: str
    page_title: str
    overall_status: str
    summary: str
    summary_insights: list[str]
    findings: list[Finding]
    page_capture_html: str
    degraded_screenshots: list[str]

    # Serialize nested dataclasses to plain dictionaries for JSON output.
    def to_dict(self) -> dict:
        report = asdict(self)
        report["findings"] = [asdict(item) for item in self.findings]
        return report


# Workflow step-level execution trace for each investigated customer.
@dataclass
class StepResult:
    name: str
    status: str
    details: str = ""
    screenshot: str = ""


@dataclass
class CustomerInvestigationResult:
    customer_name: str
    timestamp_iso: str
    status: str
    adapter_id: str = ""
    machine_ip: str = ""
    matched_datapoints: list[str] | None = None
    error_datapoints: list[str] | None = None
    evidence_account_monitoring_screenshot: str = ""
    evidence_account_monitoring_service_status_screenshot: str = ""
    evidence_account_monitoring_das_service_status_screenshot: str = ""
    evidence_das_validation_screenshot: str = ""
    evidence_das_validation_all_rows_screenshot: str = ""
    evidence_das_validation_observed_source_ids: list[str] | None = None
    evidence_das_validation_source_id_match: bool | None = None
    outcome: str = ""
    steps: list[StepResult] | None = None


# Top-level output structure for oc_workflow mode.
@dataclass
class OCWorkflowReport:
    run_id: str
    timestamp: str
    console_url: str
    downloaded_csv: str
    window_hours: int
    customers_in_window: int
    investigated_customers: int
    results: list[CustomerInvestigationResult]
    phase_logs: list[str] | None = None
    errors: list[str] | None = None

    # Convert full workflow report to a JSON-friendly dictionary.
    def to_dict(self) -> dict:
        return asdict(self)
