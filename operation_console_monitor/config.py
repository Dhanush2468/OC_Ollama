from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PreflightConfig:
    enabled: bool = True
    max_attempts: int = 5
    request_timeout_seconds: int = 3
    retry_delay_seconds: int = 2


@dataclass
class ScheduleConfig:
    mode: str = "interval"
    interval_seconds: int = 300
    timezone: str = "UTC"


@dataclass
class SkyvernConfig:
    headless: bool = True
    wait_after_load_seconds: int = 2
    navigation_timeout_seconds: int = 45
    viewport_width: int = 1920
    viewport_height: int = 1080
    extra_chromium_args: list[str] = field(default_factory=list)


@dataclass
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5vl:7b"
    timeout_seconds: int = 180
    max_page_content_chars: int = 12000
    vision_enabled: bool = True


@dataclass
class AnalysisConfig:
    max_findings: int = 5


@dataclass
class PathsConfig:
    screenshots_dir: str = "./output/screenshots"
    findings_dir: str = "./output/findings"
    logs_dir: str = "./output/logs"
    page_capture_dir: str = "./output/logs/page_captures"


@dataclass
class MonitorConfig:
    operation_console_url: str
    preflight: PreflightConfig
    schedule: ScheduleConfig
    skyvern: SkyvernConfig
    ollama: OllamaConfig
    analysis: AnalysisConfig
    paths: PathsConfig


def _merge_dataclass(cls: type[Any], data: dict[str, Any] | None) -> Any:
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
    with open(path, "r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    config = MonitorConfig(
        operation_console_url=raw.get("operation_console_url", "http://127.0.0.1:4173"),
        preflight=_merge_dataclass(PreflightConfig, raw.get("preflight")),
        schedule=_merge_dataclass(ScheduleConfig, raw.get("schedule")),
        skyvern=_merge_dataclass(SkyvernConfig, raw.get("skyvern")),
        ollama=_merge_dataclass(OllamaConfig, raw.get("ollama")),
        analysis=_merge_dataclass(AnalysisConfig, raw.get("analysis")),
        paths=_merge_dataclass(PathsConfig, raw.get("paths")),
    )
    return config


def ensure_output_directories(config: MonitorConfig) -> None:
    dirs = [
        config.paths.screenshots_dir,
        config.paths.findings_dir,
        config.paths.logs_dir,
        config.paths.page_capture_dir,
    ]
    for directory in dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
