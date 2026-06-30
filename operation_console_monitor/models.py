"""
Data Models Module
==================

Defines dataclass models for monitoring reports, findings, and workflow results.
All models support JSON serialization via to_dict() methods.

Author: Dhanush.V
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


# =============================================================================
# Monitoring Report Models
# =============================================================================


@dataclass
class Finding:
    """
    Represents a single issue or anomaly detected during monitoring.
    
    Attributes:
        timestamp: ISO format timestamp when the finding was detected
        severity: Classification level (e.g., "High", "Medium", "Low")
        issue: Brief description of the problem
        recommendation: Suggested action to resolve the issue
        evidence: Supporting details or metrics
        screenshot: File path to visual evidence
        details: Additional context or technical information
        source_view: Origin of the finding (e.g., "main", service name)
    """
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
    """
    Comprehensive report for a single monitoring run.
    
    Attributes:
        run_id: Unique identifier for this monitoring cycle
        timestamp: ISO format timestamp of the run
        console_url: Base URL of the monitored console
        page_url: Actual page URL captured (may differ after redirects)
        page_title: HTML title of the monitored page
        overall_status: Summary status ("healthy", "warning", "critical", "unknown")
        summary: Human-readable summary of findings
        summary_insights: List of key insights from analysis
        findings: Detailed list of detected issues
        page_capture_html: File path to saved HTML snapshot
        degraded_screenshots: Paths to screenshots of degraded services
    """
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
        """
        Convert report to JSON-serializable dictionary.
        
        Returns:
            Dictionary with all findings converted to nested dicts
        """
        report = asdict(self)
        report["findings"] = [asdict(item) for item in self.findings]
        return report


# =============================================================================
# Workflow Models (OC Workflow Mode)
# =============================================================================


@dataclass
class StepResult:
    """
    Execution result for a single workflow step.
    
    Attributes:
        name: Step identifier
        status: Outcome ("success", "failed", "skipped", etc.)
        details: Additional information about step execution
        screenshot: Optional visual evidence for this step
    """
    name: str
    status: str
    details: str = ""
    screenshot: str = ""


@dataclass
class CustomerInvestigationResult:
    """
    Complete investigation results for a single customer.
    
    Attributes:
        customer_name: Customer identifier
        timestamp_iso: ISO timestamp of investigation
        status: Overall investigation status
        adapter_id: Adapter identifier (if applicable)
        machine_ip: Machine IP address (if applicable)
        matched_datapoints: List of datapoints that matched validation criteria
        error_datapoints: List of datapoints with errors
        evidence_account_monitoring_screenshot: Screenshot of account monitoring view
        evidence_account_monitoring_service_status_screenshot: Service status screenshot
        evidence_account_monitoring_das_service_status_screenshot: DAS service screenshot
        evidence_das_validation_screenshot: DAS validation endpoint screenshot
        evidence_das_validation_all_rows_screenshot: Full DAS data screenshot
        evidence_das_validation_observed_source_ids: Source IDs found in DAS
        evidence_das_validation_source_id_match: Whether source ID validation passed
        outcome: Final investigation outcome classification
        steps: Detailed list of step-by-step results
    """
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


@dataclass
class OCWorkflowReport:
    """
    Top-level report for OC workflow execution mode.
    
    Attributes:
        run_id: Unique identifier for this workflow run
        timestamp: ISO format timestamp of the run
        console_url: Base URL of the operation console
        downloaded_csv: Path to downloaded CSV data file
        window_hours: Time window used for customer filtering
        customers_in_window: Total customers within the time window
        investigated_customers: Number of customers actually investigated
        results: List of individual customer investigation results
        phase_logs: Optional execution phase logs
        errors: List of errors encountered during workflow
    """
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
        """
        Convert workflow report to JSON-serializable dictionary.
        
        Returns:
            Fully nested dictionary structure ready for JSON export
        """
        return asdict(self)
