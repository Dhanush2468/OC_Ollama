from __future__ import annotations

from dataclasses import asdict, dataclass


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

    def to_dict(self) -> dict:
        report = asdict(self)
        report["findings"] = [asdict(item) for item in self.findings]
        return report


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
    outcome: str = ""
    steps: list[StepResult] | None = None


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

    def to_dict(self) -> dict:
        return asdict(self)
