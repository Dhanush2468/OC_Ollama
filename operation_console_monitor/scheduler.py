"""
Task Scheduler Module
=====================

Provides scheduling capabilities for recurring monitoring tasks.
Supports one-time and interval-based execution using APScheduler.

Author: Dhanush.V
"""

from __future__ import annotations

import argparse
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from .config import load_config
from .orchestrator import _run_once


# =============================================================================
# Scheduler Entry Point
# =============================================================================


def main() -> int:
    """
    Schedule and execute monitoring runs based on configuration.
    
    Execution modes:
        - one_time: Execute immediately and exit
        - interval: Run repeatedly at specified intervals
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        description="Schedule operation console monitoring"
    )
    parser.add_argument(
        "--config", 
        required=True, 
        help="Path to monitor.yaml configuration file"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    
    # One-time execution path (immediate single run)
    if config.schedule.mode == "one_time":
        return _run_once(args.config)

    # Recurring execution path using APScheduler
    scheduler = BlockingScheduler(timezone=ZoneInfo(config.schedule.timezone))
    scheduler.add_job(
        _run_once,
        "interval",
        seconds=max(1, config.schedule.interval_seconds),
        args=[args.config],
        max_instances=1,  # Prevent overlapping runs
        coalesce=True,    # Skip missed runs if system is busy
    )

    print(
        f"Scheduler running every {config.schedule.interval_seconds}s "
        f"in timezone {config.schedule.timezone}"
    )
    scheduler.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
