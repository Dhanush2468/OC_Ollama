"""
Dashboard Configuration Module
===============================

Configuration management for the web dashboard.

Author: Dhanush.V
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class DashboardConfig:
    """
    Dashboard-specific configuration.
    
    Attributes:
        host: Server host address
        port: Server port number
        reload: Enable auto-reload (development)
        workers: Number of worker processes
        database_path: Path to SQLite database
        page_size: Default items per page
        screenshot_cache_ttl: Screenshot cache TTL in seconds
        cors_origins: Allowed CORS origins
        monitor_config_path: Path to monitor.yaml
    """

    def __init__(self, config_dict: dict[str, Any]):
        """
        Initialize dashboard config from dictionary.
        
        Args:
            config_dict: Configuration dictionary
        """
        dashboard_config = config_dict.get("dashboard", {})
        
        self.host = dashboard_config.get("host", "0.0.0.0")
        self.port = dashboard_config.get("port", 8080)
        self.reload = dashboard_config.get("reload", False)
        self.workers = dashboard_config.get("workers", 1)
        self.database_path = dashboard_config.get("database_path", "./output/findings.db")
        self.page_size = dashboard_config.get("page_size", 50)
        self.screenshot_cache_ttl = dashboard_config.get("screenshot_cache_ttl", 3600)
        self.cors_origins = dashboard_config.get("cors_origins", [])
        
        # Store reference to monitor config path
        self.monitor_config_path = config_dict.get("_config_path", "config/monitor.yaml")


def load_dashboard_config(config_path: str) -> DashboardConfig:
    """
    Load dashboard configuration from YAML file.
    
    Args:
        config_path: Path to monitor.yaml
        
    Returns:
        DashboardConfig instance
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f) or {}
    
    # Store config path for later reference
    config_dict["_config_path"] = config_path
    
    return DashboardConfig(config_dict)
