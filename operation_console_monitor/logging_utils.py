from __future__ import annotations

import logging
from pathlib import Path


# -----------------------------------------------------------------------------
# Logger setup
# -----------------------------------------------------------------------------
# Create a shared logger that writes both to file and console.
def build_logger(logs_dir: str) -> logging.Logger:
    # Ensure log directory exists before creating file handler.
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("operation_console_monitor")
    # Reuse existing logger to avoid duplicate handlers on repeated imports.
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(Path(logs_dir) / "monitor.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
