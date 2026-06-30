"""
Logging Utilities Module
=========================

Provides centralized logging configuration for the monitoring system.
Creates a shared logger that outputs to both file and console with 
consistent formatting.

Author: Dhanush.V
"""

from __future__ import annotations

import logging
from pathlib import Path


# =============================================================================
# Logger Configuration
# =============================================================================


def build_logger(logs_dir: str) -> logging.Logger:
    """
    Create or retrieve a shared logger instance with file and console handlers.
    
    The logger writes to both:
    - File: {logs_dir}/monitor.log
    - Console: stdout
    
    Args:
        logs_dir: Directory path where log files should be stored
        
    Returns:
        Configured Logger instance
        
    Note:
        If the logger already has handlers (from previous calls), 
        the existing instance is returned to avoid duplicate handlers.
    """
    # Ensure log directory exists before creating file handler
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger("operation_console_monitor")
    
    # Reuse existing logger to avoid duplicate handlers on repeated imports
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    
    # Define consistent log format: timestamp | level | message
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    # File handler: persist logs to disk
    file_handler = logging.FileHandler(
        Path(logs_dir) / "monitor.log", 
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # Stream handler: output to console
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    
    return logger
