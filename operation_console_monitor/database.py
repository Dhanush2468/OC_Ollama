"""
Database Management Module
===========================

Provides SQLite database management for storing monitoring runs, findings,
workflow results, and screenshots. Uses SQLAlchemy ORM for type-safe queries
and connection management.

Author: Dhanush.V
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

# =============================================================================
# SQLAlchemy Base and Engine Setup
# =============================================================================

Base = declarative_base()


def _enable_wal_mode(connection, _):
    """Enable Write-Ahead Logging for better concurrent access."""
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA foreign_keys=ON")


# =============================================================================
# Database Models
# =============================================================================


class MonitoringRun(Base):
    """
    Represents a single monitoring run (either monitor or oc_workflow mode).
    
    Attributes:
        id: Run identifier (e.g., "2026-06-30-190355")
        timestamp: When the run was executed
        execution_mode: "monitor" or "oc_workflow"
        console_url: Base URL of the monitored console
        page_url: Actual page URL after navigation
        page_title: HTML page title
        overall_status: "healthy", "warning", "critical", "unknown"
        summary: Human-readable summary
        findings_count: Number of findings detected
        duration_seconds: How long the run took
        created_at: Database record creation timestamp
    """
    __tablename__ = "monitoring_runs"

    id = Column(String(50), primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    execution_mode = Column(String(20), nullable=False, index=True)
    console_url = Column(String(500), nullable=False)
    page_url = Column(String(500))
    page_title = Column(String(500))
    overall_status = Column(String(20), index=True)
    summary = Column(Text)
    findings_count = Column(Integer, default=0)
    duration_seconds = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    findings = relationship("Finding", back_populates="run", cascade="all, delete-orphan")
    workflow_results = relationship("WorkflowResult", back_populates="run", cascade="all, delete-orphan")
    screenshots = relationship("Screenshot", back_populates="run", cascade="all, delete-orphan")


class Finding(Base):
    """
    Represents a single issue or anomaly detected during monitoring.
    
    Attributes:
        id: Auto-incrementing primary key
        run_id: Foreign key to monitoring_runs
        timestamp: When the finding was detected
        severity: "Critical", "High", "Medium", "Low"
        issue: Brief description of the problem
        recommendation: Suggested action to resolve
        evidence: Supporting details or metrics
        details: Additional context
        source_view: Origin of finding (e.g., "main", service name)
        screenshot_path: Path to visual evidence
    """
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), ForeignKey("monitoring_runs.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    issue = Column(Text, nullable=False)
    recommendation = Column(Text)
    evidence = Column(Text)
    details = Column(Text)
    source_view = Column(String(100), default="main")
    screenshot_path = Column(String(500))

    # Relationships
    run = relationship("MonitoringRun", back_populates="findings")


class WorkflowResult(Base):
    """
    Stores results from OC workflow mode customer investigations.
    
    Attributes:
        id: Auto-incrementing primary key
        run_id: Foreign key to monitoring_runs
        customer_name: Customer identifier
        timestamp_iso: Investigation timestamp
        status: "investigated", "skipped", "error"
        outcome: Final classification (e.g., "NOC Report - Port Issue")
        adapter_id: Adapter identifier
        machine_ip: Machine IP address
        matched_datapoints: JSON array of matching datapoints
        error_datapoints: JSON array of error datapoints
        evidence_data: JSON object with all evidence screenshots
    """
    __tablename__ = "workflow_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), ForeignKey("monitoring_runs.id"), nullable=False, index=True)
    customer_name = Column(String(200), nullable=False, index=True)
    timestamp_iso = Column(DateTime)
    status = Column(String(50), nullable=False)
    outcome = Column(String(500))
    adapter_id = Column(String(100))
    machine_ip = Column(String(50))
    matched_datapoints = Column(Text)  # JSON array as text
    error_datapoints = Column(Text)    # JSON array as text
    evidence_data = Column(Text)       # JSON object as text

    # Relationships
    run = relationship("MonitoringRun", back_populates="workflow_results")


class Screenshot(Base):
    """
    Tracks screenshot files generated during monitoring.
    
    Attributes:
        id: Auto-incrementing primary key
        run_id: Foreign key to monitoring_runs
        customer_name: Associated customer (for oc_workflow mode)
        screenshot_type: "main", "service", "evidence"
        file_path: Absolute or relative path to screenshot
        created_at: Database record creation timestamp
    """
    __tablename__ = "screenshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), ForeignKey("monitoring_runs.id"), nullable=False, index=True)
    customer_name = Column(String(200))
    screenshot_type = Column(String(50))
    file_path = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    run = relationship("MonitoringRun", back_populates="screenshots")


# =============================================================================
# Database Manager
# =============================================================================


class DatabaseManager:
    """
    Manages database connections and provides query helpers.
    
    Thread-safe session management with proper connection pooling.
    """

    def __init__(self, database_path: str):
        """
        Initialize database manager with SQLite file path.
        
        Args:
            database_path: Path to SQLite database file
        """
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create engine with SQLite optimizations
        self.engine = create_engine(
            f"sqlite:///{self.database_path}",
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        
        # Enable WAL mode for better concurrent access
        event.listen(self.engine, "connect", _enable_wal_mode)
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

    def create_tables(self):
        """Create all database tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """
        Get a new database session.
        
        Returns:
            SQLAlchemy Session instance
            
        Usage:
            with db.get_session() as session:
                # perform database operations
                session.commit()
        """
        return self.SessionLocal()

    # =========================================================================
    # Monitoring Run Operations
    # =========================================================================

    def create_monitoring_run(
        self,
        run_id: str,
        timestamp: datetime,
        execution_mode: str,
        console_url: str,
        **kwargs,
    ) -> MonitoringRun:
        """
        Create a new monitoring run record.
        
        Args:
            run_id: Unique run identifier
            timestamp: Execution timestamp
            execution_mode: "monitor" or "oc_workflow"
            console_url: Base URL of monitored console
            **kwargs: Additional fields (page_url, overall_status, etc.)
            
        Returns:
            Created MonitoringRun instance
        """
        with self.get_session() as session:
            run = MonitoringRun(
                id=run_id,
                timestamp=timestamp,
                execution_mode=execution_mode,
                console_url=console_url,
                **kwargs,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def get_monitoring_run(self, run_id: str) -> MonitoringRun | None:
        """
        Retrieve a monitoring run by ID.
        
        Args:
            run_id: Run identifier
            
        Returns:
            MonitoringRun instance or None if not found
        """
        with self.get_session() as session:
            return session.query(MonitoringRun).filter(MonitoringRun.id == run_id).first()

    def list_monitoring_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        execution_mode: str | None = None,
        status: str | None = None,
    ) -> list[MonitoringRun]:
        """
        List monitoring runs with pagination and filters.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            execution_mode: Filter by mode ("monitor", "oc_workflow")
            status: Filter by overall_status
            
        Returns:
            List of MonitoringRun instances
        """
        with self.get_session() as session:
            query = session.query(MonitoringRun).order_by(MonitoringRun.timestamp.desc())
            
            if execution_mode:
                query = query.filter(MonitoringRun.execution_mode == execution_mode)
            if status:
                query = query.filter(MonitoringRun.overall_status == status)
            
            return query.limit(limit).offset(offset).all()

    def count_monitoring_runs(
        self,
        execution_mode: str | None = None,
        status: str | None = None,
    ) -> int:
        """
        Count monitoring runs with optional filters.
        
        Args:
            execution_mode: Filter by mode
            status: Filter by overall_status
            
        Returns:
            Total count
        """
        with self.get_session() as session:
            query = session.query(MonitoringRun)
            
            if execution_mode:
                query = query.filter(MonitoringRun.execution_mode == execution_mode)
            if status:
                query = query.filter(MonitoringRun.overall_status == status)
            
            return query.count()

    # =========================================================================
    # Finding Operations
    # =========================================================================

    def create_finding(
        self,
        run_id: str,
        timestamp: datetime,
        severity: str,
        issue: str,
        **kwargs,
    ) -> Finding:
        """
        Create a new finding record.
        
        Args:
            run_id: Associated monitoring run ID
            timestamp: Detection timestamp
            severity: Severity level
            issue: Issue description
            **kwargs: Additional fields
            
        Returns:
            Created Finding instance
        """
        with self.get_session() as session:
            finding = Finding(
                run_id=run_id,
                timestamp=timestamp,
                severity=severity,
                issue=issue,
                **kwargs,
            )
            session.add(finding)
            session.commit()
            session.refresh(finding)
            return finding

    def list_findings(
        self,
        limit: int = 50,
        offset: int = 0,
        run_id: str | None = None,
        severity: str | None = None,
        search: str | None = None,
    ) -> list[Finding]:
        """
        List findings with pagination, filters, and search.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            run_id: Filter by monitoring run
            severity: Filter by severity level
            search: Search in issue and recommendation text
            
        Returns:
            List of Finding instances
        """
        with self.get_session() as session:
            query = session.query(Finding).order_by(Finding.timestamp.desc())
            
            if run_id:
                query = query.filter(Finding.run_id == run_id)
            if severity:
                query = query.filter(Finding.severity == severity)
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    (Finding.issue.like(search_pattern)) |
                    (Finding.recommendation.like(search_pattern))
                )
            
            return query.limit(limit).offset(offset).all()

    # =========================================================================
    # Workflow Result Operations
    # =========================================================================

    def create_workflow_result(
        self,
        run_id: str,
        customer_name: str,
        status: str,
        **kwargs,
    ) -> WorkflowResult:
        """
        Create a new workflow result record.
        
        Args:
            run_id: Associated monitoring run ID
            customer_name: Customer identifier
            status: Investigation status
            **kwargs: Additional fields
            
        Returns:
            Created WorkflowResult instance
        """
        with self.get_session() as session:
            # Serialize list/dict fields to JSON
            if "matched_datapoints" in kwargs and isinstance(kwargs["matched_datapoints"], list):
                kwargs["matched_datapoints"] = json.dumps(kwargs["matched_datapoints"])
            if "error_datapoints" in kwargs and isinstance(kwargs["error_datapoints"], list):
                kwargs["error_datapoints"] = json.dumps(kwargs["error_datapoints"])
            if "evidence_data" in kwargs and isinstance(kwargs["evidence_data"], dict):
                kwargs["evidence_data"] = json.dumps(kwargs["evidence_data"])
            
            result = WorkflowResult(
                run_id=run_id,
                customer_name=customer_name,
                status=status,
                **kwargs,
            )
            session.add(result)
            session.commit()
            session.refresh(result)
            return result

    def list_workflow_results(
        self,
        run_id: str | None = None,
        customer_name: str | None = None,
    ) -> list[WorkflowResult]:
        """
        List workflow results with filters.
        
        Args:
            run_id: Filter by monitoring run
            customer_name: Filter by customer
            
        Returns:
            List of WorkflowResult instances
        """
        with self.get_session() as session:
            query = session.query(WorkflowResult)
            
            if run_id:
                query = query.filter(WorkflowResult.run_id == run_id)
            if customer_name:
                query = query.filter(WorkflowResult.customer_name == customer_name)
            
            return query.all()

    # =========================================================================
    # Screenshot Operations
    # =========================================================================

    def create_screenshot(
        self,
        run_id: str,
        file_path: str,
        **kwargs,
    ) -> Screenshot:
        """
        Create a new screenshot record.
        
        Args:
            run_id: Associated monitoring run ID
            file_path: Path to screenshot file
            **kwargs: Additional fields
            
        Returns:
            Created Screenshot instance
        """
        with self.get_session() as session:
            screenshot = Screenshot(
                run_id=run_id,
                file_path=file_path,
                **kwargs,
            )
            session.add(screenshot)
            session.commit()
            session.refresh(screenshot)
            return screenshot

    # =========================================================================
    # Statistics and Analytics
    # =========================================================================

    def get_statistics(self) -> dict[str, Any]:
        """
        Get dashboard statistics and metrics.
        
        Returns:
            Dictionary with statistics
        """
        with self.get_session() as session:
            total_runs = session.query(MonitoringRun).count()
            total_findings = session.query(Finding).count()
            
            # Count by severity
            severity_counts = {}
            for severity in ["Critical", "High", "Medium", "Low"]:
                count = session.query(Finding).filter(Finding.severity == severity).count()
                severity_counts[severity] = count
            
            # Recent runs (last 24 hours)
            recent_threshold = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            recent_runs = session.query(MonitoringRun).filter(
                MonitoringRun.timestamp >= recent_threshold
            ).count()
            
            return {
                "total_runs": total_runs,
                "total_findings": total_findings,
                "severity_counts": severity_counts,
                "recent_runs_24h": recent_runs,
            }


# =============================================================================
# Singleton Instance
# =============================================================================

# Global database manager instance
_db_manager: DatabaseManager | None = None


def get_database_manager(database_path: str | None = None) -> DatabaseManager:
    """
    Get or create the global database manager instance.
    
    Args:
        database_path: Path to database file (required on first call)
        
    Returns:
        DatabaseManager singleton instance
        
    Raises:
        ValueError: If database_path not provided on first call
    """
    global _db_manager
    
    if _db_manager is None:
        if database_path is None:
            raise ValueError("database_path required for first initialization")
        _db_manager = DatabaseManager(database_path)
        _db_manager.create_tables()
    
    return _db_manager
