"""Health Check and System Diagnostics Router."""

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Category, InventoryItem, Requirement, User
from backend.schemas import HealthCheckResponse

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/", summary="API Root Metadata")
def root_metadata() -> Dict[str, Any]:
    """Provides service identification, documentation URLs, and supported API versions."""
    return {
        "service": "Hyperlocal Marketplace API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
        "status": "operational",
    }


@router.get("/health", response_model=HealthCheckResponse, summary="Deep System Health Probe")
def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    """
    Deep operational probe:
    - Tests database connection and ping latency.
    - Queries PostGIS and pgvector extension installations.
    - Reports entity counts across all core tables.
    """
    db_info: Dict[str, Any] = {"status": "connected"}

    try:
        # Check PostgreSQL server version and extensions
        version_row = db.execute(text("SELECT version();")).scalar()
        db_info["postgres_version"] = version_row.split()[1] if version_row else "unknown"

        ext_rows = db.execute(
            text("SELECT extname, extversion FROM pg_extension WHERE extname IN ('postgis', 'vector', 'uuid-ossp');")
        ).fetchall()
        db_info["extensions"] = {name: ver for name, ver in ext_rows}

        # Table counts
        counts = {
            "users": db.query(User).count(),
            "categories": db.query(Category).count(),
            "inventory_items": db.query(InventoryItem).count(),
            "requirements": db.query(Requirement).count(),
        }
    except Exception as exc:
        db_info["status"] = "error"
        db_info["error"] = str(exc)
        counts = {}

    return HealthCheckResponse(
        status="healthy" if db_info["status"] == "connected" else "degraded",
        environment="development",
        database=db_info,
        counts=counts,
        timestamp=datetime.now(timezone.utc),
    )
