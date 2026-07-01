"""
FastAPI Application
===================

Main FastAPI application for Operation Console Monitor dashboard.

Author: Dhanush.V
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import DashboardConfig
from .dependencies import get_config

# Initialize FastAPI app
app = FastAPI(
    title="Operation Console Monitor Dashboard",
    description="Web dashboard for monitoring operation consoles",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Store app start time
app.state.start_time = time.time()

# =============================================================================
# CORS Configuration
# =============================================================================

# Get dashboard config
config: DashboardConfig = get_config()

# Add CORS middleware
if config.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# =============================================================================
# Static Files and Templates
# =============================================================================

# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Setup templates
templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# =============================================================================
# API Routes
# =============================================================================

# Import and include routers
from .routes import runs, status, statistics, findings

app.include_router(status.router, prefix="/api", tags=["Status"])
app.include_router(runs.router, prefix="/api", tags=["Runs"])
app.include_router(findings.router, prefix="/api", tags=["Findings"])
app.include_router(statistics.router, prefix="/api", tags=["Statistics"])

# =============================================================================
# Frontend Routes
# =============================================================================


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home dashboard page."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {"title": "Dashboard"},
    )


@app.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request):
    """Monitoring runs browser page."""
    return templates.TemplateResponse(
        request,
        "runs.html",
        {"title": "Monitoring Runs"},
    )


@app.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail_page(request: Request, run_id: str):
    """Run details page."""
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {"title": f"Run {run_id}", "run_id": run_id},
    )


@app.get("/findings", response_class=HTMLResponse)
async def findings_page(request: Request):
    """Findings browser page."""
    return templates.TemplateResponse(
        request,
        "findings.html",
        {"title": "Findings"},
    )


@app.get("/statistics", response_class=HTMLResponse)
async def statistics_page(request: Request):
    """Statistics and trends page."""
    return templates.TemplateResponse(
        request,
        "statistics.html",
        {"title": "Statistics"},
    )


# =============================================================================
# Health Check
# =============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    uptime = time.time() - app.state.start_time
    return {
        "status": "healthy",
        "uptime_seconds": round(uptime, 2),
        "version": "1.0.0",
    }


# =============================================================================
# Startup and Shutdown Events
# =============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    print("🚀 Dashboard starting up...")
    print(f"📊 Database: {config.database_path}")
    print(f"🌐 Server: http://{config.host}:{config.port}")
    print(f"📖 API Docs: http://{config.host}:{config.port}/api/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    print("👋 Dashboard shutting down...")
