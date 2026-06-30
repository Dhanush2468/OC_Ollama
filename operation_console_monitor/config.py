"""
Configuration Management Module
================================

Handles YAML configuration loading, validation, and directory setup.
Provides dataclass models for all configuration sections with sensible defaults.

Author: Dhanush.V
"""

from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


# =============================================================================
# Configuration Dataclass Models
# =============================================================================


@dataclass
class PreflightConfig:
    """
    Runtime preflight checks before browser automation starts.
    
    Attributes:
        enabled: Whether to perform preflight URL checks
        max_attempts: Maximum number of connection retry attempts
        request_timeout_seconds: HTTP request timeout per attempt
        retry_delay_seconds: Delay between retry attempts
    """
    enabled: bool = True
    max_attempts: int = 5
    request_timeout_seconds: int = 3
    retry_delay_seconds: int = 2


@dataclass
class ScheduleConfig:
    """
    Scheduling configuration for recurring monitoring.
    
    Attributes:
        mode: Execution mode ("interval" or "one_time")
        interval_seconds: Time between monitoring cycles (interval mode)
        timezone: Timezone for scheduling (e.g., "UTC", "America/New_York")
    """
    mode: str = "interval"
    interval_seconds: int = 300
    timezone: str = "UTC"


@dataclass
class SkyvernConfig:
    """
    Browser automation settings via Skyvern/Playwright.
    
    Attributes:
        headless: Run browser in headless mode (no GUI)
        wait_after_load_seconds: Wait time for dynamic content to load
        navigation_timeout_seconds: Maximum time for page navigation
        viewport_width: Browser viewport width in pixels
        viewport_height: Browser viewport height in pixels
        extra_chromium_args: Additional command-line arguments for Chromium
    """
    headless: bool = True
    wait_after_load_seconds: int = 2
    navigation_timeout_seconds: int = 45
    viewport_width: int = 1920
    viewport_height: int = 1080
    extra_chromium_args: list[str] = field(default_factory=list)


@dataclass
class OllamaConfig:
    """
    Ollama AI model configuration for content analysis.
    
    Attributes:
        base_url: Ollama API endpoint URL
        model: Model identifier (e.g., "qwen2.5vl:7b")
        timeout_seconds: Maximum time for model inference
        max_page_content_chars: Character limit for HTML content analysis
        vision_enabled: Whether to use vision capabilities (screenshots)
    """
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5vl:7b"
    timeout_seconds: int = 180
    max_page_content_chars: int = 12000
    vision_enabled: bool = True


@dataclass
class AnalysisConfig:
    """
    Analysis output configuration.
    
    Attributes:
        max_findings: Maximum number of findings to include in report
    """
    max_findings: int = 5


@dataclass
class OCWorkflowConfig:
    """
    Configuration for OC workflow execution mode.
    
    Attributes:
        window_hours: Time window for customer filtering (hours)
        no_window_fraction: Fraction of total customers to use if window filtering fails
        timestamp_column: CSV column name for timestamps
        customer_column: CSV column name for customer identifiers
        das_state_filter: DAS state to filter (e.g., "faulted")
        max_customers_per_run: Maximum customers to investigate per run
        downloaded_csv_glob: Glob pattern for finding downloaded CSV files
        datapoints_reference_file: Path to reference datapoints file for validation
        login_wait_seconds: Wait time after login attempt
        step_timeout_seconds: Timeout for individual workflow steps
    """
    window_hours: int = 24
    no_window_fraction: float = 0.0
    timestamp_column: str = "timestamp"
    customer_column: str = "customer"
    das_state_filter: str = "faulted"
    max_customers_per_run: int = 50
    downloaded_csv_glob: str = "*.csv"
    datapoints_reference_file: str = ""
    login_wait_seconds: int = 90
    step_timeout_seconds: int = 12


@dataclass
class PathsConfig:
    """
    File system paths for output artifacts.
    
    Attributes:
        screenshots_dir: Directory for screenshot storage
        findings_dir: Directory for JSON findings/reports
        logs_dir: Directory for log files
        page_capture_dir: Directory for HTML page captures
        downloads_dir: Directory for downloaded files (CSV exports, etc.)
    """
    screenshots_dir: str = "./output/screenshots"
    findings_dir: str = "./output/findings"
    logs_dir: str = "./output/logs"
    page_capture_dir: str = "./output/logs/page_captures"
    downloads_dir: str = "./output/downloads"


@dataclass
class MonitorConfig:
    """
    Top-level monitoring configuration container.
    
    Attributes:
        operation_console_url: Base URL of the operation console to monitor
        execution_mode: Execution mode ("monitor" or "oc_workflow")
        preflight: Preflight check configuration
        schedule: Scheduling configuration
        skyvern: Browser automation configuration
        ollama: AI model configuration
        analysis: Analysis output configuration
        oc_workflow: OC workflow mode configuration
        paths: File system paths configuration
    """
    operation_console_url: str
    execution_mode: str
    preflight: PreflightConfig
    schedule: ScheduleConfig
    skyvern: SkyvernConfig
    ollama: OllamaConfig
    analysis: AnalysisConfig
    oc_workflow: OCWorkflowConfig
    paths: PathsConfig


# =============================================================================
# Configuration Loading Functions
# =============================================================================


def _merge_dataclass(cls: type[Any], data: dict[str, Any] | None) -> Any:
    """
    Build dataclass instances by merging user values over defaults.
    
    Args:
        cls: Dataclass type to instantiate
        data: User-provided values (from YAML)
        
    Returns:
        Instance of cls with merged values
    """
    values = data or {}
    merged: dict[str, Any] = {}
    
    for field_info in fields(cls):
        if field_info.name in values:
            merged[field_info.name] = values[field_info.name]
        elif field_info.default is not MISSING:
            merged[field_info.name] = field_info.default
        elif field_info.default_factory is not MISSING:  # type: ignore[attr-defined]
            merged[field_info.name] = field_info.default_factory()
            
    return cls(**merged)


def load_config(path: str) -> MonitorConfig:
    """
    Load and parse YAML configuration file.
    
    Args:
        path: File path to monitor.yaml configuration
        
    Returns:
        Fully populated MonitorConfig instance
        
    Raises:
        FileNotFoundError: If configuration file doesn't exist
        yaml.YAMLError: If YAML is malformed
    """
    config_dir = Path(path).resolve().parent.parent

    with open(path, "r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    paths_config = _merge_dataclass(PathsConfig, raw.get("paths"))
    # Resolve relative paths against the project root (parent of the config directory)
    # so the agent runs correctly regardless of the working directory.
    for attr in ("screenshots_dir", "findings_dir", "logs_dir", "page_capture_dir", "downloads_dir"):
        value = getattr(paths_config, attr)
        resolved = (config_dir / value).resolve()
        setattr(paths_config, attr, str(resolved))

    oc_workflow_config = _merge_dataclass(OCWorkflowConfig, raw.get("oc_workflow"))
    if oc_workflow_config.datapoints_reference_file:
        oc_workflow_config.datapoints_reference_file = str(
            (config_dir / oc_workflow_config.datapoints_reference_file).resolve()
        )

    config = MonitorConfig(
        operation_console_url=raw.get("operation_console_url", "http://127.0.0.1:4173"),
        execution_mode=str(raw.get("execution_mode", "monitor")),
        preflight=_merge_dataclass(PreflightConfig, raw.get("preflight")),
        schedule=_merge_dataclass(ScheduleConfig, raw.get("schedule")),
        skyvern=_merge_dataclass(SkyvernConfig, raw.get("skyvern")),
        ollama=_merge_dataclass(OllamaConfig, raw.get("ollama")),
        analysis=_merge_dataclass(AnalysisConfig, raw.get("analysis")),
        oc_workflow=oc_workflow_config,
        paths=paths_config,
    )
    return config


def ensure_output_directories(config: MonitorConfig) -> None:
    """
    Create all required output directories before any write operation.
    
    Args:
        config: Monitoring configuration containing path definitions
    """
    dirs = [
        config.paths.screenshots_dir,
        config.paths.findings_dir,
        config.paths.logs_dir,
        config.paths.page_capture_dir,
        config.paths.downloads_dir,
    ]
    for directory in dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
