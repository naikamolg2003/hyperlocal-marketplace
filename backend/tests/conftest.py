"""
Shared pytest fixtures and test configuration for Hyperlocal Marketplace.
"""

import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Ensure workspace root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.main import app
from backend.database import SessionLocal, engine, get_db
from sqlalchemy import text
from backend.models import User, UserRole, Category, InventoryItem, SubscriptionStatus

# Ensure users.subscription_status column is VARCHAR(50) to support 'trial', 'active', 'expired'
try:
    with engine.begin() as _conn:
        _conn.execute(text("ALTER TABLE users ALTER COLUMN subscription_status TYPE VARCHAR(50) USING subscription_status::text;"))
        _conn.execute(text("ALTER TABLE users ALTER COLUMN subscription_status SET DEFAULT 'trial';"))
except Exception as _e:
    pass


@pytest.fixture(scope="session")
def test_client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session():
    """Direct SQLAlchemy database session fixture with teardown."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def make_unique_phone():
    """Factory fixture to generate unique mock phone numbers."""
    def _generator(prefix: str = "98"):
        suffix = uuid.uuid4().int % 100000000
        return f"+91{prefix}{suffix:08d}"
    return _generator


@pytest.fixture
def sample_location():
    """Central test coordinate: Indiranagar, Bangalore."""
    return {
        "name": "Indiranagar Central",
        "latitude": 12.9784,
        "longitude": 77.6408,
    }
