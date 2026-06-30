"""
Findings API Routes
===================

Findings browsing and search endpoints.

Author: Dhanush.V
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query

from operation_console_monitor.database import DatabaseManager

from ..dependencies import get_db
from ..models import FindingListResponse, FindingResponse

router = APIRouter()


@router.get("/findings", response_model=FindingListResponse)
async def list_findings(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    run_id: str | None = Query(None, description="Filter by run ID"),
    severity: str | None = Query(None, description="Filter by severity"),
    search: str | None = Query(None, description="Search in issue/recommendation"),
    db: DatabaseManager = Depends(get_db),
):
    """
    List findings with pagination, filters, and search.
    
    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        run_id: Filter by monitoring run
        severity: Filter by severity level
        search: Search text in issue and recommendation
        
    Returns:
        Paginated list of findings
    """
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get findings from database
    findings = db.list_findings(
        limit=page_size,
        offset=offset,
        run_id=run_id,
        severity=severity,
        search=search,
    )
    
    # For total count, we need to implement a count method
    # For now, estimate based on results
    # TODO: Add count_findings method to database manager
    total = len(findings) if len(findings) < page_size else (page * page_size + 1)
    
    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    # Convert to response models
    items = [FindingResponse.from_orm(finding) for finding in findings]
    
    return FindingListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
