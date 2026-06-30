"""
Operation Console Monitor Package
===================================

A local-only monitoring solution for operation consoles using:
- Skyvern for browser automation
- Ollama + Qwen 2.5 VL for AI-powered analysis
- Python orchestrator for scheduling and workflows

Author: Dhanush.V
License: MIT
"""

__version__ = "1.0.0"
__all__ = [
    "config",
    "logging_utils",
    "models",
    "ollama_analysis",
    "orchestrator",
    "scheduler",
    "skyvern_capture",
    "oc_workflow",
]
