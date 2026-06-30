#!/usr/bin/env python3
"""
Dashboard Launcher
==================

Starts the FastAPI dashboard server.

Usage:
    python run_dashboard.py --config config/monitor.yaml

Author: Dhanush.V
"""

import argparse
import sys

import uvicorn


def main():
    """Main entry point for dashboard server."""
    parser = argparse.ArgumentParser(
        description="Start Operation Console Monitor Dashboard"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/monitor.yaml",
        help="Path to monitor.yaml configuration file",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind to (default: 8080)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    
    args = parser.parse_args()
    
    # Set config path environment variable
    import os
    os.environ["MONITOR_CONFIG_PATH"] = args.config
    
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║        Operation Console Monitor - Web Dashboard                 ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(f"\n🌐 Starting dashboard on http://{args.host}:{args.port}")
    print(f"📖 API Documentation: http://{args.host}:{args.port}/api/docs")
    print(f"⚙️  Configuration: {args.config}\n")
    
    # Start uvicorn server
    uvicorn.run(
        "dashboard.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    sys.exit(main())
