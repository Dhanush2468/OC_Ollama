"""
Shared Dependencies
===================

Dependency injection for FastAPI endpoints.

Author: Dhanush.V
"""

from __future__ import annotations

from functools import lru_cache

from operation_console_monitor.database import DatabaseManager, get_database_manager

from .config import DashboardConfig, load_dashboard_config


# =============================================================================
# Configuration Dependencies
# =============================================================================


@lru_cache()
def get_config() -> DashboardConfig:
    """
    Get cached dashboard configuration.
    
    Returns:
        DashboardConfig instance
    """
    return load_dashboard_config("config/monitor.yaml")


# =============================================================================
# Database Dependencies
# =============================================================================


def get_db() -> DatabaseManager:
    """
    Get database manager instance.
    
    Returns:
        DatabaseManager instance
        
    Usage:
        @app.get("/api/runs")
        def list_runs(db: DatabaseManager = Depends(get_db)):
            return db.list_monitoring_runs()
    """
    config = get_config()
    return get_database_manager(config.database_path)
