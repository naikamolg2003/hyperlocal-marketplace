-- =============================================================================
-- Hyperlocal Marketplace - Core Database DDL Schema & Fixtures
-- Generated for PostgreSQL 16 + PostGIS 3 + pgvector
-- Matches SQLAlchemy models in backend/models.py
-- =============================================================================

-- Ensure required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. Custom Enum Types
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role_enum') THEN
        CREATE TYPE user_role_enum AS ENUM ('customer', 'seller', 'admin');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'requirement_status_enum') THEN
        CREATE TYPE requirement_status_enum AS ENUM ('draft', 'submitted', 'broadcasting', 'fulfilled', 'cancelled');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscription_status_enum') THEN
        CREATE TYPE subscription_status_enum AS ENUM ('active_trial', 'pending_payment', 'trial_expired', 'subscribed');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_status_enum') THEN
        CREATE TYPE order_status_enum AS ENUM ('pending', 'accepted', 'completed', 'cancelled');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'quotation_status_enum') THEN
        CREATE TYPE quotation_status_enum AS ENUM ('pending', 'accepted', 'rejected');
    END IF;
END $$;

-- 2. Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(120) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    role user_role_enum NOT NULL DEFAULT 'customer',
    location GEOMETRY(Point, 4326),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    address TEXT,
    subscription_status subscription_status_enum NOT NULL DEFAULT 'active_trial',
    completed_orders_count INTEGER NOT NULL DEFAULT 0,
    free_orders_remaining INTEGER NOT NULL DEFAULT 2,
    subscription_expires_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Spatial index on user coordinates for sub-millisecond hyperlocal radius filtering
CREATE INDEX IF NOT EXISTS idx_users_location ON users USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users (phone);

-- 3. Categories Table
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100) NOT NULL,
    sub_category VARCHAR(100),
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_category_sub_category UNIQUE (category, sub_category)
);

CREATE INDEX IF NOT EXISTS idx_categories_category ON categories (category);
CREATE INDEX IF NOT EXISTS idx_categories_sub_category ON categories (sub_category);

-- 4. Inventory Items Table
CREATE TABLE IF NOT EXISTS inventory_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    seller_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_name VARCHAR(255) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inventory_items_seller_id ON inventory_items (seller_id);
CREATE INDEX IF NOT EXISTS idx_inventory_items_product_name ON inventory_items (product_name);
CREATE INDEX IF NOT EXISTS idx_inventory_items_is_available ON inventory_items (is_available);

-- 5. Item Categories Association Table (Many-to-Many Mapping)
-- Allows a product to be mapped to multiple categories without duplicating inventory_items
CREATE TABLE IF NOT EXISTS item_categories (
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (item_id, category_id)
);

CREATE INDEX IF NOT EXISTS idx_item_categories_item ON item_categories (item_id);
CREATE INDEX IF NOT EXISTS idx_item_categories_category ON item_categories (category_id);

-- 6. Requirements Table (Customer Demand / Natural Language Requests)
CREATE TABLE IF NOT EXISTS requirements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    raw_text TEXT NOT NULL,
    structured_json JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'BROADCASTED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_requirements_customer ON requirements (customer_id);
CREATE INDEX IF NOT EXISTS idx_requirements_status ON requirements (status);
CREATE INDEX IF NOT EXISTS idx_requirements_structured_json ON requirements USING GIN (structured_json);

-- 7. Quotations Table (Vendor Price Quotes for Specific Customer Requirements)
CREATE TABLE IF NOT EXISTS quotations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requirement_id UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    seller_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    itemized_prices JSONB NOT NULL,
    total_amount NUMERIC(10, 2) NOT NULL,
    estimated_delivery_time VARCHAR(100) NOT NULL,
    status quotation_status_enum NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quotations_requirement ON quotations (requirement_id);
CREATE INDEX IF NOT EXISTS idx_quotations_seller ON quotations (seller_id);
CREATE INDEX IF NOT EXISTS idx_quotations_status ON quotations (status);

-- 8. Orders Table (Order Fulfillment, Itemized Quotes & Freemium Quota Tracking)
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requirement_id UUID REFERENCES requirements(id) ON DELETE SET NULL,
    quotation_id UUID REFERENCES quotations(id) ON DELETE SET NULL,
    seller_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quote_amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'ACCEPTED',
    notes TEXT,
    itemized_quote JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_seller ON orders (seller_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_requirement ON orders (requirement_id);
CREATE INDEX IF NOT EXISTS idx_orders_quotation ON orders (quotation_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);

CREATE INDEX IF NOT EXISTS idx_quotations_requirement ON quotations (requirement_id);
CREATE INDEX IF NOT EXISTS idx_quotations_seller ON quotations (seller_id);
CREATE INDEX IF NOT EXISTS idx_quotations_status ON quotations (status);

-- =============================================================================
-- Initial Fixture Data (Seeding)
-- =============================================================================
INSERT INTO users (id, name, phone, role, location, latitude, longitude, address)
VALUES 
    (
        'a0000000-0000-0000-0000-000000000001',
        'Green Valley Organic Store',
        '+919876543210',
        'seller',
        ST_SetSRID(ST_MakePoint(77.6408, 12.9784), 4326),
        12.9784,
        77.6408,
        '100 Feet Rd, Indiranagar, Bengaluru, Karnataka 560038'
    ),
    (
        'a0000000-0000-0000-0000-000000000002',
        'Anita Sharma',
        '+919123456789',
        'customer',
        ST_SetSRID(ST_MakePoint(77.6412, 12.9716), 4326),
        12.9716,
        77.6412,
        'Defence Colony, Indiranagar, Bengaluru, Karnataka 560038'
    ),
    (
        'a0000000-0000-0000-0000-000000000003',
        'Platform Admin',
        '+919000000000',
        'admin',
        ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326),
        12.9716,
        77.5946,
        'Hyperlocal HQ, Bengaluru'
    )
ON CONFLICT (phone) DO NOTHING;

-- Seed Categories
INSERT INTO categories (id, category, sub_category, description)
VALUES 
    ('b0000000-0000-0000-0000-000000000001', 'Daily Essentials', 'Dairy & Breakfast', 'Milk, curd, butter, paneer'),
    ('b0000000-0000-0000-0000-000000000002', 'Groceries', 'Organic Staples', 'Organic pulses, flours, grains'),
    ('b0000000-0000-0000-0000-000000000003', 'Beverages', 'Fresh Juices', 'Cold pressed natural juices')
ON CONFLICT (category, sub_category) DO NOTHING;

-- Seed Inventory Items
INSERT INTO inventory_items (id, seller_id, product_name, price, is_available)
VALUES 
    (
        'c0000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000001',
        'A2 Organic Farm Fresh Whole Milk (1 Litre)',
        72.00,
        TRUE
    ),
    (
        'c0000000-0000-0000-0000-000000000002',
        'a0000000-0000-0000-0000-000000000001',
        'Organic Sona Masoori Unpolished Rice (5 kg)',
        385.00,
        TRUE
    ),
    (
        'c0000000-0000-0000-0000-000000000003',
        'a0000000-0000-0000-0000-000000000001',
        'Fresh Pomegranate Cold Pressed Juice (300 ml)',
        120.00,
        FALSE
    )
ON CONFLICT (id) DO NOTHING;

-- Seed Multi-Category Mapping (Farm Fresh Milk is in BOTH Daily Essentials AND Groceries)
INSERT INTO item_categories (item_id, category_id, is_primary)
VALUES 
    ('c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', TRUE),
    ('c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', FALSE),
    ('c0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000002', TRUE),
    ('c0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000003', TRUE),
    ('c0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000001', FALSE)
ON CONFLICT (item_id, category_id) DO NOTHING;

-- Seed Customer Requirement
INSERT INTO requirements (id, customer_id, raw_text, structured_json, status)
VALUES 
    (
        'd0000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000002',
        'Need 2 litres of fresh whole milk and 5kg sona masoori rice delivered within 2 hours',
        '{"items": [{"name": "whole milk", "quantity": 2, "unit": "L", "preferred_category": "Dairy & Breakfast"}, {"name": "sona masoori rice", "quantity": 5, "unit": "kg", "preferred_category": "Groceries"}], "urgency_minutes": 120, "max_radius_km": 3.0}'::jsonb,
        'submitted'
    )
ON CONFLICT (id) DO NOTHING;
