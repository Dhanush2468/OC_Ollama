"""
Status API Routes
=================

System status and health monitoring endpoints.

Author: Dhanush.V
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends

from operation_console_monitor.database import DatabaseManager

from ..dependencies import get_config, get_db
from ..models import SystemStatusResponse

router = APIRouter()


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(db: DatabaseManager = Depends(get_db)):
    """
    Get current system status.
    
    Returns:
        System status including last run info and database size
    """
    config = get_config()
    
    # Get latest run
    runs = db.list_monitoring_runs(limit=1)
    last_run = runs[0] if runs else None
    
    # Calculate database size
    db_path = Path(config.database_path)
    db_size_mb = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0
    
    return SystemStatusResponse(
        status="idle",  # Could be enhanced to check if orchestrator is running
        last_run_id=last_run.id if last_run else None,
        last_run_timestamp=last_run.timestamp if last_run else None,
        last_run_status=last_run.overall_status if last_run else None,
        database_size_mb=round(db_size_mb, 2),
    )
