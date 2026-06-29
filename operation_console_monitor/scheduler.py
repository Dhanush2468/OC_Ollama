from __future__ import annotations

import argparse
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from .config import load_config
from .orchestrator import _run_once


# -----------------------------------------------------------------------------
# Scheduler entrypoint
# -----------------------------------------------------------------------------
# Runs once or on interval based on schedule settings from config.
def main() -> int:
    parser = argparse.ArgumentParser(description="Schedule operation console monitoring")
    parser.add_argument("--config", required=True, help="Path to monitor.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    if config.schedule.mode == "one_time":
        # Immediate single execution path.
        return _run_once(args.config)

    # Recurring execution path using APScheduler interval trigger.
    scheduler = BlockingScheduler(timezone=ZoneInfo(config.schedule.timezone))
    scheduler.add_job(
        _run_once,
        "interval",
        seconds=max(1, config.schedule.interval_seconds),
        args=[args.config],
        max_instances=1,
        coalesce=True,
    )

    print(
        f"Scheduler running every {config.schedule.interval_seconds}s "
        f"in timezone {config.schedule.timezone}"
    )
    scheduler.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
