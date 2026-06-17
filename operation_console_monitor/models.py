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
