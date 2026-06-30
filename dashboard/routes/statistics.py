"""
Statistics API Routes
=====================

Dashboard statistics and analytics endpoints.

Author: Dhanush.V
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from operation_console_monitor.database import DatabaseManager

from ..dependencies import get_db
from ..models import StatisticsResponse

router = APIRouter()


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(db: DatabaseManager = Depends(get_db)):
    """
    Get dashboard statistics and metrics.
    
    Returns:
        Dashboard statistics including run counts, findings by severity, etc.
    """
    # Get base statistics from database
    stats = db.get_statistics()
    
    # Calculate additional metrics
    critical_findings = stats["severity_counts"].get("Critical", 0)
    high_findings = stats["severity_counts"].get("High", 0)
    
    # Determine health status based on critical/high findings
    if critical_findings > 0:
        health_status = "critical"
    elif high_findings > 0:
        health_status = "warning"
    else:
        health_status = "healthy"
    
    return StatisticsResponse(
        total_runs=stats["total_runs"],
        total_findings=stats["total_findings"],
        severity_counts=stats["severity_counts"],
        recent_runs_24h=stats["recent_runs_24h"],
        critical_findings=critical_findings,
        high_findings=high_findings,
        health_status=health_status,
    )
