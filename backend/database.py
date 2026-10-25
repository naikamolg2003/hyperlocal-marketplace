"""
Database Engine & Session Management for Hyperlocal Marketplace.
Configures SQLAlchemy connection pooling, environment resolution, and FastAPI session dependency.
"""

import os
from pathlib import Path
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# -----------------------------------------------------------------------------
# Environment Resolution: checks backend/.env first, then root .env
# -----------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent

backend_env = BACKEND_DIR / ".env"
root_env = ROOT_DIR / ".env"

if backend_env.exists():
    load_dotenv(backend_env)
elif root_env.exists():
    load_dotenv(root_env)
else:
    load_dotenv()

# Extract connection parameters
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres_dev_password_change_in_prod")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "hyperlocal_marketplace")

# Prefer explicit DATABASE_URL if defined, otherwise construct from components
DEFAULT_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# Ensure modern SQLAlchemy driver dialect with psycopg2
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# -----------------------------------------------------------------------------
# SQLAlchemy Engine with Connection Pooling
# -----------------------------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    pool_pre_ping=True,  # Proactively validates connections before checkout
    echo=os.getenv("DB_ECHO_SQL", "false").lower() in ("true", "1", "yes"),
)

# Thread-local Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base for ORM Models
Base = declarative_base()


# -----------------------------------------------------------------------------
# FastAPI Dependency for Session Lifecycle
# -----------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a thread-safe database session
    and automatically closing it after request processing.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> dict:
    """
    Validates database connectivity and returns engine metadata.
    """
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version(), current_database(), now();")).fetchone()
        return {
            "status": "connected",
            "database": result[1],
            "server_version": result[0],
            "server_time": str(result[2]),
        }
