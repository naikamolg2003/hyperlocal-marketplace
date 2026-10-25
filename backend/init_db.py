"""
Database Initialization & Seeding Utility for Hyperlocal Marketplace.
Creates all SQLAlchemy models and tables in the PostgreSQL/PostGIS database,
verifies geospatial indices, and optionally seeds initial demo data.

Usage:
    python -m backend.init_db
    python -m backend.init_db --seed
    python -m backend.init_db --drop-all --seed
"""

import argparse
import sys
from sqlalchemy import text
from sqlalchemy.orm import Session

# Ensure backend package imports resolve
from backend.database import Base, engine, SessionLocal
from backend.models import User, UserRole, Category, InventoryItem, Requirement, RequirementStatus, item_categories


def verify_extensions(db: Session):
    """Ensures PostGIS and pgvector extensions are active."""
    print("-> Verifying PostgreSQL extensions...")
    result = db.execute(text("SELECT extname, extversion FROM pg_extension WHERE extname IN ('postgis', 'vector', 'uuid-ossp');")).fetchall()
    found = {row[0]: row[1] for row in result}
    print(f"   Found extensions: {found}")
    
    missing = [ext for ext in ['postgis', 'vector', 'uuid-ossp'] if ext not in found]
    if missing:
        print(f"-> Enabling missing extensions: {missing}")
        for ext in missing:
            db.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}";'))
        db.commit()


def init_database(drop_all: bool = False):
    """Creates all defined database tables."""
    with SessionLocal() as db:
        verify_extensions(db)

    if drop_all:
        print("-> [WARNING] Dropping all existing tables...")
        Base.metadata.drop_all(bind=engine)

    print("-> Creating database tables from SQLAlchemy models...")
    Base.metadata.create_all(bind=engine)
    print("   Tables created successfully:")
    for table_name in Base.metadata.tables.keys():
        print(f"    - {table_name}")


def seed_database():
    """Populates database with initial verified test fixtures."""
    print("\n-> Seeding initial demo fixtures...")
    with SessionLocal() as db:
        # Check if already seeded
        existing_users = db.query(User).count()
        if existing_users > 0:
            print("   Database already contains user records. Skipping duplicate seeding.")
            return

        # 1. Seed Users (Seller & Customer with PostGIS Coordinates)
        print("   1. Creating users (Seller & Customer with PostGIS locations)...")
        seller = User(
            name="Green Valley Organic Store",
            phone="+919876543210",
            role=UserRole.SELLER,
            address="100 Feet Rd, Indiranagar, Bengaluru, Karnataka 560038",
        )
        # Coordinates: Bangalore Indiranagar (Lat 12.9784, Lon 77.6408)
        seller.set_coordinates(lat=12.9784, lon=77.6408)

        customer = User(
            name="Anita Sharma",
            phone="+919123456789",
            role=UserRole.CUSTOMER,
            address="Defence Colony, Indiranagar, Bengaluru, Karnataka 560038",
        )
        # Coordinates: ~1.2 km away from seller (Lat 12.9716, Lon 77.6412)
        customer.set_coordinates(lat=12.9716, lon=77.6412)

        admin = User(
            name="Platform Admin",
            phone="+919000000000",
            role=UserRole.ADMIN,
            address="Hyperlocal HQ, Bengaluru",
        )
        admin.set_coordinates(lat=12.9716, lon=77.5946)

        db.add_all([seller, customer, admin])
        db.flush()

        # 2. Seed Categories
        print("   2. Creating multi-taxonomy categories...")
        cat_dairy = Category(category="Daily Essentials", sub_category="Dairy & Breakfast", description="Milk, curd, butter, paneer")
        cat_groceries = Category(category="Groceries", sub_category="Organic Staples", description="Organic pulses, flours, grains")
        cat_beverages = Category(category="Beverages", sub_category="Fresh Juices", description="Cold pressed natural juices")

        db.add_all([cat_dairy, cat_groceries, cat_beverages])
        db.flush()

        # 3. Seed Inventory Items with Multiple Category Mapping
        print("   3. Creating inventory items mapped across multiple categories...")
        # Item 1: Farm Fresh Milk (Mapped to BOTH 'Daily Essentials' AND 'Groceries')
        milk_item = InventoryItem(
            seller_id=seller.id,
            product_name="A2 Organic Farm Fresh Whole Milk (1 Litre)",
            price=72.00,
            is_available=True,
        )
        milk_item.categories.extend([cat_dairy, cat_groceries])

        # Item 2: Organic Sona Masoori Rice (Mapped to 'Groceries')
        rice_item = InventoryItem(
            seller_id=seller.id,
            product_name="Organic Sona Masoori Unpolished Rice (5 kg)",
            price=385.00,
            is_available=True,
        )
        rice_item.categories.append(cat_groceries)

        # Item 3: Pomegranate Cold-Pressed Juice (Mapped to 'Beverages' & 'Daily Essentials')
        juice_item = InventoryItem(
            seller_id=seller.id,
            product_name="Fresh Pomegranate Cold Pressed Juice (300 ml)",
            price=120.00,
            is_available=False,  # Toggle demo
        )
        juice_item.categories.extend([cat_beverages, cat_dairy])

        db.add_all([milk_item, rice_item, juice_item])
        db.flush()

        # 4. Seed Customer Requirement (Natural Language + Parsed JSON)
        print("   4. Creating customer requirement with natural language & JSON...")
        req = Requirement(
            customer_id=customer.id,
            raw_text="Need 2 litres of fresh whole milk and 5kg sona masoori rice delivered within 2 hours",
            structured_json={
                "items": [
                    {"name": "whole milk", "quantity": 2, "unit": "L", "preferred_category": "Dairy & Breakfast"},
                    {"name": "sona masoori rice", "quantity": 5, "unit": "kg", "preferred_category": "Groceries"}
                ],
                "urgency_minutes": 120,
                "max_radius_km": 3.0
            },
            status=RequirementStatus.SUBMITTED,
        )
        db.add(req)
        db.commit()

        print("-> Seeding completed successfully!")
        print(f"   Created Seller     : {seller.name} ({seller.id})")
        print(f"   Created Customer   : {customer.name} ({customer.id})")
        print(f"   Created Item       : {milk_item.product_name} (Mapped to: {[c.category for c in milk_item.categories]})")
        print(f"   Created Requirement: {req.raw_text[:50]}... (Status: {req.status.value})")


def verify_tables():
    """Prints verification summary of tables and row counts."""
    print("\n-> Verifying created tables and row counts:")
    with SessionLocal() as db:
        for model in [User, Category, InventoryItem, Requirement]:
            count = db.query(model).count()
            print(f"   - {model.__tablename__:<16}: {count} rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hyperlocal Database Initializer")
    parser.add_argument("--drop-all", action="store_true", help="Drop existing tables before recreating")
    parser.add_argument("--seed", action="store_true", help="Seed initial sample test data")
    args = parser.parse_args()

    try:
        init_database(drop_all=args.drop_all)
        if args.seed:
            seed_database()
        verify_tables()
        print("\n[SUCCESS] Database initialization completed.")
    except Exception as e:
        print(f"\n[ERROR] Database initialization failed: {e}", file=sys.stderr)
        sys.exit(1)
