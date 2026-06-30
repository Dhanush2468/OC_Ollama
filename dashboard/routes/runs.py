"""
Runs API Routes
===============

Monitoring runs browsing and management endpoints.

Author: Dhanush.V
"""

from __future__ import annotations

import json
import math

from fastapi import APIRouter, Depends, HTTPException, Query

from operation_console_monitor.database import DatabaseManager

from ..dependencies import get_config, get_db
from ..models import MonitoringRunListResponse, MonitoringRunResponse, WorkflowResultResponse

router = APIRouter()


@router.get("/runs", response_model=MonitoringRunListResponse)
async def list_runs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    execution_mode: str | None = Query(None, description="Filter by execution mode"),
    status: str | None = Query(None, description="Filter by overall status"),
    db: DatabaseManager = Depends(get_db),
):
    """
    List monitoring runs with pagination and filters.
    
    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        execution_mode: Filter by mode ("monitor", "oc_workflow")
        status: Filter by overall_status
        
    Returns:
        Paginated list of monitoring runs
    """
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get runs from database
    runs = db.list_monitoring_runs(
        limit=page_size,
        offset=offset,
        execution_mode=execution_mode,
        status=status,
    )
    
    # Get total count
    total = db.count_monitoring_runs(
        execution_mode=execution_mode,
        status=status,
    )
    
    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    # Convert to response models
    items = [MonitoringRunResponse.from_orm(run) for run in runs]
    
    return MonitoringRunListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/runs/{run_id}", response_model=MonitoringRunResponse)
async def get_run(
    run_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """
    Get details for a specific monitoring run.
    
    Args:
        run_id: Run identifier
        
    Returns:
        Monitoring run details
        
    Raises:
        HTTPException: If run not found
    """
    run = db.get_monitoring_run(run_id)
    
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return MonitoringRunResponse.from_orm(run)


@router.get("/runs/{run_id}/workflow-results", response_model=list[WorkflowResultResponse])
async def get_workflow_results(
    run_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """
    Get workflow results for a specific run (OC workflow mode only).
    
    Args:
        run_id: Run identifier
        
    Returns:
        List of workflow results
    """
    results = db.list_workflow_results(run_id=run_id)
    
    # Parse JSON fields
    response_items = []
    for result in results:
        # Parse JSON strings to Python objects
        matched_datapoints = []
        error_datapoints = []
        evidence_data = {}
        
        try:
            if result.matched_datapoints:
                matched_datapoints = json.loads(result.matched_datapoints)
        except (json.JSONDecodeError, TypeError):
            pass
        
        try:
            if result.error_datapoints:
                error_datapoints = json.loads(result.error_datapoints)
        except (json.JSONDecodeError, TypeError):
            pass
        
        try:
            if result.evidence_data:
                evidence_data = json.loads(result.evidence_data)
        except (json.JSONDecodeError, TypeError):
            pass
        
        response_items.append(
            WorkflowResultResponse(
                id=result.id,
                run_id=result.run_id,
                customer_name=result.customer_name,
                timestamp_iso=result.timestamp_iso,
                status=result.status,
                outcome=result.outcome,
                adapter_id=result.adapter_id,
                machine_ip=result.machine_ip,
                matched_datapoints=matched_datapoints,
                error_datapoints=error_datapoints,
                evidence_data=evidence_data,
            )
        )
    
    return response_items
