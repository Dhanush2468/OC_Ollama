#!/usr/bin/env python3
"""
Database Migration Script
==========================

Migrates existing JSON findings and workflow results into SQLite database.
Preserves all historical data and supports both monitor and oc_workflow modes.

Usage:
    python migrate_to_database.py --findings-dir output/findings --database output/findings.db

Author: Dhanush.V
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from operation_console_monitor.database import DatabaseManager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse ISO format timestamp string.
    
    Args:
        timestamp_str: ISO format timestamp
        
    Returns:
        datetime object
    """
    try:
        # Try ISO format with seconds
        return datetime.fromisoformat(timestamp_str)
    except ValueError:
        try:
            # Try alternative formats
            return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Fallback: use current time
            logger.warning(f"Could not parse timestamp: {timestamp_str}, using current time")
            return datetime.utcnow()


def migrate_monitor_mode_run(db: DatabaseManager, json_path: Path) -> bool:
    """
    Migrate a monitor mode JSON file to database.
    
    Args:
        db: DatabaseManager instance
        json_path: Path to JSON file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        run_id = data.get("run_id")
        if not run_id:
            logger.warning(f"Missing run_id in {json_path}")
            return False
        
        # Check if already migrated
        existing = db.get_monitoring_run(run_id)
        if existing:
            logger.debug(f"Run {run_id} already exists, skipping")
            return True
        
        # Create monitoring run
        timestamp = parse_timestamp(data.get("timestamp"))
        run = db.create_monitoring_run(
            run_id=run_id,
            timestamp=timestamp,
            execution_mode="monitor",
            console_url=data.get("console_url", ""),
            page_url=data.get("page_url", ""),
            page_title=data.get("page_title", ""),
            overall_status=data.get("overall_status", "unknown"),
            summary=data.get("summary", ""),
            findings_count=len(data.get("findings", [])),
        )
        
        # Create findings
        findings = data.get("findings", [])
        for finding_data in findings:
            db.create_finding(
                run_id=run_id,
                timestamp=parse_timestamp(finding_data.get("timestamp")),
                severity=finding_data.get("severity", "Unknown"),
                issue=finding_data.get("issue", ""),
                recommendation=finding_data.get("recommendation", ""),
                evidence=finding_data.get("evidence", ""),
                details=finding_data.get("details", ""),
                source_view=finding_data.get("source_view", "main"),
                screenshot_path=finding_data.get("screenshot", ""),
            )
        
        # Create screenshot records
        screenshot_path = data.get("page_capture_html", "").replace(".html", ".png")
        if screenshot_path:
            db.create_screenshot(
                run_id=run_id,
                file_path=screenshot_path,
                screenshot_type="main",
            )
        
        # Degraded service screenshots
        for screenshot_path in data.get("degraded_screenshots", []):
            db.create_screenshot(
                run_id=run_id,
                file_path=screenshot_path,
                screenshot_type="service",
            )
        
        logger.info(f"✓ Migrated monitor run: {run_id} ({len(findings)} findings)")
        return True
        
    except Exception as exc:
        logger.error(f"Error migrating {json_path}: {exc}")
        return False


def migrate_oc_workflow_run(db: DatabaseManager, json_path: Path) -> bool:
    """
    Migrate an OC workflow JSON file to database.
    
    Args:
        db: DatabaseManager instance
        json_path: Path to JSON file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        run_id = data.get("run_id")
        if not run_id:
            logger.warning(f"Missing run_id in {json_path}")
            return False
        
        # Check if already migrated
        existing = db.get_monitoring_run(run_id)
        if existing:
            logger.debug(f"Run {run_id} already exists, skipping")
            return True
        
        # Create monitoring run
        timestamp = parse_timestamp(data.get("timestamp"))
        run = db.create_monitoring_run(
            run_id=run_id,
            timestamp=timestamp,
            execution_mode="oc_workflow",
            console_url=data.get("console_url", ""),
            overall_status="complete",
            summary=f"Investigated {data.get('investigated_customers', 0)} customers",
            findings_count=0,  # OC workflow doesn't have traditional findings
        )
        
        # Create workflow results
        results = data.get("results", [])
        for result_data in results:
            customer_name = result_data.get("customer_name", "Unknown")
            
            # Prepare evidence data
            evidence_data = {
                "account_monitoring_screenshot": result_data.get("evidence_account_monitoring_screenshot", ""),
                "service_status_screenshot": result_data.get("evidence_account_monitoring_service_status_screenshot", ""),
                "das_service_screenshot": result_data.get("evidence_account_monitoring_das_service_status_screenshot", ""),
                "das_validation_screenshot": result_data.get("evidence_das_validation_screenshot", ""),
                "das_all_rows_screenshot": result_data.get("evidence_das_validation_all_rows_screenshot", ""),
                "das_source_ids": result_data.get("evidence_das_validation_observed_source_ids", []),
                "das_source_id_match": result_data.get("evidence_das_validation_source_id_match"),
            }
            
            timestamp_iso = result_data.get("timestamp_iso")
            db.create_workflow_result(
                run_id=run_id,
                customer_name=customer_name,
                timestamp_iso=parse_timestamp(timestamp_iso) if timestamp_iso else None,
                status=result_data.get("status", "unknown"),
                outcome=result_data.get("outcome", ""),
                adapter_id=result_data.get("adapter_id", ""),
                machine_ip=result_data.get("machine_ip", ""),
                matched_datapoints=result_data.get("matched_datapoints", []),
                error_datapoints=result_data.get("error_datapoints", []),
                evidence_data=evidence_data,
            )
            
            # Create screenshot records for all evidence
            for key, path in evidence_data.items():
                if path and isinstance(path, str) and path.strip():
                    db.create_screenshot(
                        run_id=run_id,
                        customer_name=customer_name,
                        file_path=path,
                        screenshot_type="evidence",
                    )
        
        logger.info(f"✓ Migrated OC workflow run: {run_id} ({len(results)} customers)")
        return True
        
    except Exception as exc:
        logger.error(f"Error migrating {json_path}: {exc}")
        return False


def migrate_findings_directory(findings_dir: Path, database_path: Path) -> tuple[int, int]:
    """
    Migrate all JSON files from findings directory to database.
    
    Args:
        findings_dir: Path to findings directory
        database_path: Path to SQLite database
        
    Returns:
        Tuple of (success_count, error_count)
    """
    logger.info(f"Starting migration from {findings_dir} to {database_path}")
    
    # Initialize database
    db = DatabaseManager(str(database_path))
    db.create_tables()
    logger.info("Database initialized")
    
    # Find all JSON files (exclude summary.json)
    json_files = [
        f for f in findings_dir.glob("*.json")
        if f.name != "summary.json"
    ]
    
    logger.info(f"Found {len(json_files)} JSON files to migrate")
    
    success_count = 0
    error_count = 0
    
    for json_path in sorted(json_files):
        try:
            # Read JSON to determine mode
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            execution_mode = data.get("execution_mode")
            
            # Migrate based on mode
            if execution_mode == "oc_workflow" or "results" in data:
                success = migrate_oc_workflow_run(db, json_path)
            else:
                success = migrate_monitor_mode_run(db, json_path)
            
            if success:
                success_count += 1
            else:
                error_count += 1
                
        except Exception as exc:
            logger.error(f"Error processing {json_path}: {exc}")
            error_count += 1
    
    logger.info(f"Migration complete: {success_count} successful, {error_count} errors")
    
    # Show statistics
    stats = db.get_statistics()
    logger.info(f"Database statistics:")
    logger.info(f"  Total runs: {stats['total_runs']}")
    logger.info(f"  Total findings: {stats['total_findings']}")
    logger.info(f"  Severity breakdown: {stats['severity_counts']}")
    
    return success_count, error_count


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate JSON findings to SQLite database"
    )
    parser.add_argument(
        "--findings-dir",
        type=Path,
        default=Path("output/findings"),
        help="Path to findings directory (default: output/findings)",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("output/findings.db"),
        help="Path to SQLite database (default: output/findings.db)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Validate findings directory
    if not args.findings_dir.exists():
        logger.error(f"Findings directory not found: {args.findings_dir}")
        return 1
    
    # Run migration
    success, errors = migrate_findings_directory(args.findings_dir, args.database)
    
    if errors == 0:
        logger.info("✅ Migration completed successfully!")
        return 0
    else:
        logger.warning(f"⚠️  Migration completed with {errors} errors")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
