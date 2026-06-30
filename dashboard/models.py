"""
Pydantic Models for API
========================

Request and response models for FastAPI endpoints.

Author: Dhanush.V
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Monitoring Run Models
# =============================================================================


class MonitoringRunResponse(BaseModel):
    """Response model for a monitoring run."""
    
    id: str
    timestamp: datetime
    execution_mode: str
    console_url: str
    page_url: str | None = None
    page_title: str | None = None
    overall_status: str | None = None
    summary: str | None = None
    findings_count: int = 0
    duration_seconds: float | None = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class MonitoringRunListResponse(BaseModel):
    """Paginated list of monitoring runs."""
    
    items: list[MonitoringRunResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# Finding Models
# =============================================================================


class FindingResponse(BaseModel):
    """Response model for a finding."""
    
    id: int
    run_id: str
    timestamp: datetime
    severity: str
    issue: str
    recommendation: str | None = None
    evidence: str | None = None
    details: str | None = None
    source_view: str = "main"
    screenshot_path: str | None = None
    
    class Config:
        from_attributes = True


class FindingListResponse(BaseModel):
    """Paginated list of findings."""
    
    items: list[FindingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# Workflow Result Models
# =============================================================================


class WorkflowResultResponse(BaseModel):
    """Response model for workflow result."""
    
    id: int
    run_id: str
    customer_name: str
    timestamp_iso: datetime | None = None
    status: str
    outcome: str | None = None
    adapter_id: str | None = None
    machine_ip: str | None = None
    matched_datapoints: list[str] = Field(default_factory=list)
    error_datapoints: list[str] = Field(default_factory=list)
    evidence_data: dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        from_attributes = True


# =============================================================================
# Statistics Models
# =============================================================================


class StatisticsResponse(BaseModel):
    """Dashboard statistics."""
    
    total_runs: int
    total_findings: int
    severity_counts: dict[str, int]
    recent_runs_24h: int
    
    # Additional computed stats
    critical_findings: int = 0
    high_findings: int = 0
    health_status: str = "healthy"


# =============================================================================
# Status Models
# =============================================================================


class SystemStatusResponse(BaseModel):
    """Current system status."""
    
    status: str  # "running", "idle", "error"
    last_run_id: str | None = None
    last_run_timestamp: datetime | None = None
    last_run_status: str | None = None
    uptime_seconds: float | None = None
    database_size_mb: float | None = None


# =============================================================================
# Configuration Models
# =============================================================================


class ConfigResponse(BaseModel):
    """Configuration view."""
    
    operation_console_url: str
    execution_mode: str
    schedule_interval_seconds: int
    ollama_model: str
    dashboard_port: int


class TriggerRunRequest(BaseModel):
    """Request to trigger a manual monitoring run."""
    
    mode: str = Field(default="monitor", description="Execution mode: monitor or oc_workflow")
    config_path: str = Field(default="config/monitor.yaml", description="Path to config file")


class TriggerRunResponse(BaseModel):
    """Response from triggering a run."""
    
    status: str
    message: str
    run_id: str | None = None
