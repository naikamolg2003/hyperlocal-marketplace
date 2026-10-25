"""
Main FastAPI Application Entrypoint for Hyperlocal Marketplace.

Features:
- PostGIS spherical spatial radius queries (/api/v1/items/nearby, /api/v1/requirements/nearby).
- Multi-category inventory taxonomy and stock toggles.
- Customer requirement natural language submission and lifecycle.
- Deep health diagnostic probe (/health).
- Interactive OpenAPI docs available at /docs and /redoc.
"""

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from backend.database import engine, test_connection
from backend.routers import billing, categories, health, inventory, orders, quotations, requirements, users

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hyperlocal-backend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler verifying database connectivity on server launch."""
    logger.info("Initializing Hyperlocal Marketplace backend...")
    connected = test_connection()
    if connected:
        logger.info("Database connectivity established successfully.")
    else:
        logger.warning("Database connection check failed on startup. Please ensure PostgreSQL is reachable.")
    yield
    logger.info("Shutting down Hyperlocal Marketplace backend...")
    engine.dispose()
    logger.info("Database engine connection pool disposed.")


# OpenAPI Tags Metadata
tags_metadata = [
    {
        "name": "Health & Diagnostics",
        "description": "Deep database and operational probe verifying PostgreSQL, PostGIS, pgvector, and table metrics.",
    },
    {
        "name": "Users",
        "description": "Customer, Seller, and Admin registration and geospatial coordinate management.",
    },
    {
        "name": "Categories",
        "description": "Product category and sub-category taxonomy management.",
    },
    {
        "name": "Inventory & Spatial Search",
        "description": "Product catalog and PostGIS-powered nearby radius search (e.g. 3 km delivery perimeter).",
    },
    {
        "name": "Customer Requirements",
        "description": "Natural language customer demand ingestion, structured JSON parsing, and broadcast discovery.",
    },
]

app = FastAPI(
    title="Hyperlocal Marketplace API",
    description=(
        "Production-grade FastAPI backend powering a hyperlocal commerce engine. "
        "Leverages PostgreSQL 16 with PostGIS for sub-millisecond geodesic radius matching "
        "and pgvector for semantic search."
    ),
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits local frontend development (Vite, Next.js, mobile apps)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error("SQLAlchemy database error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred while processing your request."},
    )


@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )


# Include Sub-Routers
app.include_router(health.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(inventory.router)
app.include_router(requirements.router)
app.include_router(billing.router)
app.include_router(quotations.router)
app.include_router(orders.router)

# Direct root aliases for requirements
from backend.schemas import NearbyRequirementsResponse, RequirementSubmitResponse
app.add_api_route(
    "/requirements/submit",
    requirements.submit_requirement,
    methods=["POST"],
    response_model=RequirementSubmitResponse,
    tags=["Customer Requirements"],
    summary="Submit Requirement with AI Parsing & 3 km Geospatial Matching (Root Route)",
    status_code=status.HTTP_201_CREATED,
)
app.add_api_route(
    "/requirements/nearby",
    requirements.search_nearby_requirements,
    methods=["GET"],
    response_model=NearbyRequirementsResponse,
    tags=["Customer Requirements"],
    summary="Nearby Demands for Merchants (Root Route)",
)
app.add_api_route(
    "/requirements/broadcasts/seller/{seller_id}",
    requirements.get_seller_broadcasts,
    methods=["GET"],
    response_model=NearbyRequirementsResponse,
    tags=["Customer Requirements"],
    summary="Get Active Requirement Broadcasts for Seller (Root Route)",
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
