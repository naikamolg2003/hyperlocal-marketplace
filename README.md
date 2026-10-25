# Hyperlocal Marketplace - Database Infrastructure

A production-ready, containerized PostgreSQL 16 database environment engineered for high-performance geospatial filtering and AI-driven vector search.

---

## Architecture Overview

> **Detailed System Architecture & Diagrams**:
> - [ARCHITECTURE.md](file:///e:/hyperlocal-marketplace/ARCHITECTURE.md): Multi-tier architecture diagram, 6-stage data flow, and demand lifecycle sequence diagram.
> - [ARCHITECTURE_v2.md](file:///e:/hyperlocal-marketplace/ARCHITECTURE_v2.md): Production-hardened enterprise architecture incorporating Phone OTP/JWT auth, licensed split-settlement payments, doorstep delivery OTP, 11-state order lifecycle, inventory auto-quoting, Redis task queues, and India DPDP Act 2023 compliance.

This database setup integrates two mission-critical PostgreSQL extensions:

1. **[PostGIS](https://postgis.net/) (v3.4+)**: Enables geographic objects and high-speed spatial calculations. Crucial for our **3 km hyperlocal radius filter**, vendor discovery, customer distance computations, and spatial clustering using spatial indexing (GiST).
2. **[pgvector](https://github.com/pgvector/pgvector) (v0.7+)**: Enables vector embeddings storage, exact / approximate nearest neighbor search (HNSW and IVFFlat), and cosine/L2 similarity matching for semantic catalog search and recommendation engines.

Both extensions are packaged on top of the official Debian-based PostgreSQL 16 engine with automated startup initialization and health checking.

---

## Prerequisites

- [Docker Engine](https://docs.docker.com/engine/install/) (v20.10+) or [Docker Desktop](https://www.docker.com/products/docker-desktop/) / [Rancher Desktop](https://rancherdesktop.io/)
- [Docker Compose](https://docs.docker.com/compose/) (v2.0+)

---

## Quickstart

### 1. One-Click Setup & Machine Replication (Recommended)

To set up the entire environment on a new machine, or to repair/rebuild a corrupted installation, run the automated setup wizard. It validates Docker prerequisites, auto-generates `.env`, builds the custom PostgreSQL 16 image, starts containers, waits for health checks, and executes an automated test suite verifying PostGIS (3km radius query), pgvector, and UUID generation.

#### On Windows (PowerShell):
```powershell
# First-time setup or replication on a new machine
.\setup.ps1

# Repair / Rebuild if installation breaks or corrupts (fresh image build without cache)
.\setup.ps1 -Repair -NoCache

# Complete factory reset including database volume (CAUTION: wipes database)
.\setup.ps1 -Repair -ResetData -Force
```

#### On Linux / macOS / WSL:
```bash
./scripts/setup.sh
```

---

### 2. Manual Environment Configuration (Optional)

If you prefer to configure manually:
```bash
# On Linux / macOS:
cp .env.example .env

# On Windows (PowerShell):
Copy-Item .env.example .env
```

---

### 3. Start the Database (Automated Scripts)

You can launch and stop the complete stack using the automated operational scripts. The startup script executes pre-flight checks, builds/starts containers, monitors healthcheck status, verifies extensions, and writes all commands and container logs in verbose mode to `logs/startup_<timestamp>.log` (also mirrored to `logs/startup_latest.log`).

#### On Windows (PowerShell):
```powershell
# Start the database and log all output
.\start.ps1

# Or with options:
.\start.ps1 -NoBuild               # Skip image rebuild
```

#### On Linux / macOS / WSL:
```bash
./scripts/start.sh
```

---

### 4. Health & Server Metrics Monitoring (On-Demand Diagnostics)

At any time, inspect real-time container health, CPU/Memory/IO metrics, disk usage, active database queries, cache hit ratios, and server uptime:

#### On Windows (PowerShell):
```powershell
.\health.ps1
```

#### On Linux / macOS / WSL:
```bash
./scripts/health.sh
```

All output and commands are mirrored to `logs/health_latest.log`.

---

### 5. Stop the Database (Automated Scripts)

Gracefully shuts down containers, captures pre-shutdown metrics/connections, removes networks, and logs all shutdown activities to `logs/shutdown_<timestamp>.log` (mirrored to `logs/shutdown_latest.log`).

#### On Windows (PowerShell):
```powershell
# Graceful shutdown (preserves database data)
.\stop.ps1

# Or with options:
.\stop.ps1 -TimeoutSeconds 30      # Custom timeout
.\stop.ps1 -Volumes                # WARNING: removes persistent postgres_data volume
```

#### On Linux / macOS / WSL:
```bash
./scripts/stop.sh
```

---

### 5. Manual Docker Commands (Alternative)

If you prefer using direct Docker CLI commands:

```bash
# Start manually
docker compose up -d --build

# Tail logs manually
docker compose logs -f db

# Stop manually
docker compose down
```

---

### 3. Verify Container Status & Health

Check that the container is up and running in a `healthy` state:

```bash
docker compose ps
```

You should see:
```text
NAME                 IMAGE                         COMMAND                  SERVICE   CREATED         STATUS                   PORTS
hyperlocal-postgres  hyperlocal-marketplace-db:16  "docker-entrypoint.s…"   db        10 seconds ago  Up 9 seconds (healthy)   0.0.0.0:5432->5432/tcp
```

> **Note on Healthchecks**: The container runs an automated `pg_isready` check every 10 seconds to ensure the database engine is accepting client connections before reporting healthy.

---

### 4. Connecting to the Database

#### Option A: Interactive CLI via Docker Exec (No local tools required)

Open a `psql` console directly inside the running container:

```bash
docker compose exec -it db psql -U postgres -d hyperlocal_marketplace
```

*(If you customized `DB_USER` or `DB_NAME` in `.env`, substitute those values above).*

#### Option B: From Host via `psql`

```bash
psql -h localhost -p 5432 -U postgres -d hyperlocal_marketplace
```

#### Option C: GUI Database Clients (DBeaver, TablePlus, DataGrip, pgAdmin)

- **Host**: `localhost` (or `127.0.0.1`)
- **Port**: `5432`
- **Database**: `hyperlocal_marketplace`
- **Username**: `postgres`
- **Password**: `postgres_dev_password_change_in_prod` (or your value from `.env`)
- **SSL Mode**: `disable` (for local development)

#### Option D: Application Connection String (Prisma, Drizzle, TypeORM, SQLAlchemy)

```text
postgresql://postgres:postgres_dev_password_change_in_prod@localhost:5432/hyperlocal_marketplace?sslmode=disable
```

---

## Verifying Extensions & Sample Queries

Once connected via `psql` or your GUI client, run the verification queries below:

### 1. Verify Installed Extensions

```sql
SELECT extname, extversion 
FROM pg_extension 
WHERE extname IN ('postgis', 'vector', 'uuid-ossp');
```

Expected output:
```text
  extname  | extversion 
-----------+------------
 postgis   | 3.6.4
 vector    | 0.8.7
 uuid-ossp | 1.1
```

---

### 2. PostGIS Verification: 3 km Hyperlocal Radius Filter

Demonstration: Storing store coordinates as `GEOGRAPHY(Point, 4326)` and querying vendors within a **3,000-meter (3 km)** radius of a user's location.

```sql
-- Create sample stores table
CREATE TABLE IF NOT EXISTS stores (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    location GEOGRAPHY(Point, 4326) NOT NULL
);

-- Create a GiST spatial index for high-speed radius lookups
CREATE INDEX IF NOT EXISTS idx_stores_location ON stores USING GIST (location);

-- Insert sample stores (longitude, latitude)
INSERT INTO stores (name, location) VALUES
    ('Downtown Bakery', ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326)),       -- Point A (Origin)
    ('Corner Grocery (1.5 km)', ST_SetSRID(ST_MakePoint(77.6046, 12.9750), 4326)), -- ~1.2 km away
    ('Far Suburb Mart (8 km)', ST_SetSRID(ST_MakePoint(77.6600, 12.9900), 4326));  -- ~8 km away

-- Query: Find all stores within 3 km (3000 meters) of user location (77.5946, 12.9716)
SELECT 
    name,
    ROUND(ST_Distance(location, ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326))::numeric, 2) AS distance_meters
FROM stores
WHERE ST_DWithin(
    location,
    ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326),
    3000 -- 3 km in meters
)
ORDER BY distance_meters ASC;
```

---

### 3. pgvector Verification: Embeddings & Similarity Search

Demonstration: Storing 3-dimensional vector embeddings and computing L2 distance `<->` and cosine distance `<=>`.

```sql
-- Test vector computation directly
SELECT '[1,2,3]'::vector <-> '[4,5,6]'::vector AS euclidean_distance;
SELECT '[1,2,3]'::vector <=> '[4,5,6]'::vector AS cosine_distance;

-- Create sample product items with vector embeddings (e.g. 1536 dims for OpenAI or 768 for open embeddings)
CREATE TABLE IF NOT EXISTS product_embeddings (
    id SERIAL PRIMARY KEY,
    title VARCHAR(150),
    embedding vector(3)
);

-- Insert sample product vectors
INSERT INTO product_embeddings (title, embedding) VALUES
    ('Organic Apples', '[0.8, 0.1, 0.2]'),
    ('Fresh Bananas',  '[0.75, 0.15, 0.1]'),
    ('Laptop Stand',   '[0.05, 0.9, 0.85]');

-- Semantic query: Find top 2 products most similar to query vector '[0.82, 0.12, 0.18]'
SELECT 
    title,
    embedding <=> '[0.82, 0.12, 0.18]' AS cosine_similarity_distance
FROM product_embeddings
ORDER BY cosine_similarity_distance ASC
LIMIT 2;
```

---

## FastAPI Backend Architecture & Database Models

The `/backend` module provides the core data layer for the Python FastAPI application, integrating SQLAlchemy 2.0 with GeoAlchemy2 (PostGIS) and pgvector.

### 1. Directory Structure

```text
backend/
├── __init__.py           # Package indicator
├── main.py               # FastAPI application entrypoint, CORS & error handling
├── requirements.txt      # Core dependencies (FastAPI, SQLAlchemy, GeoAlchemy2, httpx, etc.)
├── database.py           # Engine setup, connection pooling, and FastAPI get_db dependency
├── models.py             # SQLAlchemy models (users, categories, inventory_items, requirements)
├── schemas.py            # Pydantic v2 validation DTOs and serialization models
├── crud.py               # PostGIS spatial queries, ST_DWithin filtering & business logic
├── ai_parser.py          # LLM customer requirement parser (Gemini, OpenAI, Anthropic, fallback)
├── matching_engine.py    # 3 km PostGIS matching engine & seller inventory scoring
├── init_db.py            # CLI database table creator and test data seeder
├── schema.sql            # Direct SQL DDL with GiST spatial indexes & test fixtures
├── test_api.py           # Automated end-to-end API integration test suite
└── routers/
    ├── __init__.py
    ├── health.py         # /health deep diagnostic probe & / root metadata
    ├── users.py          # /api/v1/users onboarding & geospatial profile management
    ├── categories.py     # /api/v1/categories product taxonomy management
    ├── inventory.py      # /api/v1/items catalog & PostGIS /nearby radius search
    └── requirements.py   # /api/v1/requirements demand ingestion & /nearby broadcasting
```

### 2. Core Tables & Schemas

| Table | Purpose | Key Attributes |
| :--- | :--- | :--- |
| **`users`** | Customers, Sellers & Admins | `id` (UUID), `name`, `phone`, `role` (`customer`, `seller`, `admin`), `location` (PostGIS `POINT` in EPSG:4326), `latitude`, `longitude`, `created_at`. Indexed with **GiST** for sub-millisecond 3km radius calculations. |
| **`categories`** | Normalized product taxonomies | `id` (UUID), `category`, `sub_category`, `description`. Enforces unique pairs `(category, sub_category)`. |
| **`inventory_items`** | Seller product catalog | `id` (UUID), `seller_id` (FK `users`), `product_name`, `price`, `is_available` (boolean toggle), `created_at`. |
| **`item_categories`** | Many-to-Many association | `item_id`, `category_id`, `is_primary`. **Allows a seller to map a single product to multiple categories without duplicate inventory rows.** |
| **`requirements`** | Customer demand broadcasts | `id` (UUID), `customer_id` (FK `users`), `raw_text` (natural language request), `structured_json` (JSONB parsed items/bounds), `status` (`submitted`, `broadcasting`, `fulfilled`, etc.). |

---

### 3. API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/health` | Deep health probe verifying PostgreSQL 16, PostGIS, pgvector, and table metrics. |
| **GET** | `/` | API service identification and OpenAPI documentation URLs. |
| **POST** | `/requirements/submit` | **Core AI & 3 km Matching Engine**: Ingests customer natural language shopping text, triggers AI parser, persists requirement, queries PostGIS 3 km radius (`ST_DWithin`), scores local merchant inventories, and broadcasts alert. |
| **POST** | `/api/v1/requirements/submit` | Versioned alias for `/requirements/submit`. |
| **POST** | `/api/v1/users` | Register customer/seller with automatic PostGIS `POINT(lon, lat)` spatial sync. |
| **GET** | `/api/v1/users` | List users with optional `role` and `is_active` filters and pagination. |
| **GET** | `/api/v1/users/{id}` | Get full user profile and geospatial coordinates. |
| **PUT** | `/api/v1/users/{id}` | Update profile; recalculates PostGIS geometry point and GiST index. |
| **POST** | `/api/v1/categories` | Create category and sub-category pair (idempotent). |
| **GET** | `/api/v1/categories` | Retrieve complete taxonomy catalog. |
| **POST** | `/api/v1/items` | Publish seller inventory item linked to multiple category IDs. |
| **GET** | `/api/v1/items/nearby` | **Hyperlocal Spatial Search**: Query available items within `radius_km` of `(lat, lon)` using PostGIS `ST_DWithin` & geodesic `ST_Distance`. |
| **GET** | `/api/v1/items/seller/{id}` | Retrieve complete inventory catalog for a specific merchant. |
| **PATCH**| `/api/v1/items/{id}/availability` | Fast boolean toggle for in-stock item availability. |
| **POST** | `/api/v1/requirements` | Submit customer pre-structured requirement with structured JSON payload. |
| **GET** | `/api/v1/requirements/nearby` | Merchant demand discovery: active customer requirements within `radius_km`. |
| **PATCH**| `/api/v1/requirements/{id}/status` | Lifecycle transitions (`submitted` -> `broadcasting` -> `fulfilled`). |
| **PATCH**| `/api/v1/requirements/{id}/status` | Lifecycle transitions (`submitted` -> `broadcasting` -> `fulfilled`). |

---

### 4. Running the Full-Stack Application (Backend + Frontend)

To experience the complete AI-powered hyperlocal quick-commerce engine, launch the FastAPI backend and React frontend concurrently in two terminal sessions:

#### Terminal 1: Launch FastAPI Backend (Port 8000)
```powershell
# Windows (PowerShell):
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000

# Linux / macOS:
PYTHONPATH=. uvicorn backend.main:app --reload --port 8000
```
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Probe**: [http://localhost:8000/health](http://localhost:8000/health)

#### Terminal 2: Launch React + Tailwind Frontend (Port 3000)
```powershell
cd frontend-web
npm run dev
```
- **Frontend Web Portal**: [http://localhost:3000](http://localhost:3000)
  - **Customer Portal**: Natural language prompt input, Wakad / Indiranagar GPS presets, AI structured shopping list, and 3 km local merchant broadcast.
  - **Seller Dashboard**: Real-time 3 km radar feed of incoming customer demands, order acceptance, and custom price quoting.

---

### 5. Running Automated API Integration Tests

Execute the comprehensive end-to-end integration test suite verifying health, category management, user geocoding, PostGIS hyperlocal nearby radius queries, and customer demand lifecycles:

```powershell
# On Windows:
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe backend/test_api.py

# On Linux / macOS:
PYTHONPATH=. python backend/test_api.py
```

---

### 6. Freemium Seller Subscription & Order Quota Lifecycle

Our hyperlocal marketplace implements a **seller freemium lifecycle**:
- **Free Trial**: Every new merchant begins with `active_trial` status and **2 free completed orders** (`free_orders_remaining: 2`).
- **Automated Threshold Trigger**: When a merchant fulfills their **2nd successful order** (`POST /api/v1/orders/complete`), the backend automatically updates their status to `pending_payment` / `trial_expired`.
- **Broadcast Gating**: While in `pending_payment` or `trial_expired`, the merchant's `can_receive_broadcasts` flag is set to `false`, pausing them from receiving new customer demand broadcasts within their 3 km radius.
- **Platform Subscription Fee (Rs. 1,000/month)**: The merchant pays the Rs. 1,000 platform subscription fee via `POST /api/v1/billing/seller/{seller_id}/pay`, which transitions their status to `subscribed` for 30 days and restores full broadcast receiving.

#### How to Run the Automated Freemium Lifecycle Test:
A standalone end-to-end test script verifies this complete sequence:
```powershell
# Windows (PowerShell):
.\.venv\Scripts\python.exe C:\Users\HomePC\.gemini\antigravity-ide\brain\970a8fcb-1713-44d1-b79c-62ec81f6871b\scratch\test_freemium_billing.py

# Linux / macOS:
python scratch/test_freemium_billing.py
```

#### Manual / Step-by-Step API Testing Guide:

1. **Check Initial Seller Billing Status**:
   ```bash
   curl -X GET "http://localhost:8000/api/v1/billing/seller/<SELLER_UUID>/status"
   ```
   *Expected Response:*
   ```json
   {
     "seller_id": "<SELLER_UUID>",
     "seller_name": "Fresh Test Grocers",
     "subscription_status": "active_trial",
     "completed_orders_count": 0,
     "free_orders_remaining": 2,
     "can_receive_broadcasts": true
   }
   ```

2. **Complete 1st Order**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/orders/complete" \
     -H "Content-Type: application/json" \
     -d '{"seller_id": "<SELLER_UUID>", "quote_amount": 76.0, "notes": "Order 1 fulfilled"}'
   ```
   *Result:* `completed_orders_count = 1`, `free_orders_remaining = 1`, `subscription_status = "active_trial"`.

3. **Complete 2nd Order (Triggers Automated Freemium Gate)**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/orders/complete" \
     -H "Content-Type: application/json" \
     -d '{"seller_id": "<SELLER_UUID>", "quote_amount": 114.0, "notes": "Order 2 fulfilled"}'
   ```
   *Result:*
   - `completed_orders_count = 2`, `free_orders_remaining = 0`
   - `subscription_status = "pending_payment"`
   - `can_receive_broadcasts = false`
   - `trial_expired_alert = true`

4. **Verify Broadcast Lockout**:
   Submit a customer requirement within 3 km of the seller via `POST /requirements/submit`. The seller appears with `can_receive_broadcasts: false` and is excluded from broadcast notifications.

5. **Simulate Platform Fee Payment (Rs. 1,000/month)**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/billing/seller/<SELLER_UUID>/pay" \
     -H "Content-Type: application/json" \
     -d '{"amount": 1000.0, "payment_method": "upi", "transaction_ref": "UPI-TXN-98437218"}'
   ```
   *Result:* Status upgrades to `"subscribed"`, `can_receive_broadcasts = true`, and `subscription_expires_at` is set 30 days ahead.

---

### 7. Mobile App Scaffolding (`/frontend-mobile` - React Native / Expo)

A cross-platform React Native customer mobile app built with Expo, targeting Android, iOS, and Web.

#### Features:
- **Natural Language Shopping Requirement**: Large multiline input supporting English, Hindi, and Hinglish demand descriptions with one-tap prompt chips.
- **Location Selector & 3 km Perimeter**: Preset selector for Wakad (Pune), Indiranagar (Bangalore), and Custom GPS coordinates.
- **AI Shopping List Summary**: Displays structured shopping list items (quantities, units, categories, urgency levels, constraints).
- **Nearby Merchant Match Cards**: Displays local stores within 3 km, geodesic distance (meters), match percentages, in-stock catalog products, and broadcast dispatch status.
- **Configurable Backend Host**: Built-in settings modal allowing connection switching between Android Emulator (`http://10.0.2.2:8000`), iOS Simulator / Web (`http://localhost:8000`), or LAN IP for physical device testing via Expo Go.

#### How to Run the Mobile App Locally:

```bash
# Navigate to mobile project
cd frontend-mobile

# Install dependencies (if not already installed)
npm install

# Start the Expo development server
npm start
# or: npx expo start
```

#### Running on Devices & Emulators:
- **Android Emulator**: Ensure an Android AVD is running, then press `a` in the terminal.
- **iOS Simulator**: (macOS only) Press `i` in the terminal.
- **Physical Device (Expo Go)**: Install **Expo Go** from Google Play Store or Apple App Store. Scan the QR code displayed in the terminal. Ensure your phone and development machine are connected to the same Wi-Fi network, and update the API URL via the in-app pill to your machine's LAN IP (`http://192.168.x.x:8000`).
- **Web Browser**: Press `w` in the terminal to open the mobile interface in your desktop browser.

---

### 8. Backend Setup & Dependency Installation

#### Step 1: Create and Activate Virtual Environment

##### On Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

##### On Linux / macOS / WSL:
```bash
python3 -m venv venv
source venv/bin/activate
```

#### Step 2: Install Backend Dependencies

```bash
pip install -r backend/requirements.txt
```

---

### 9. Initializing Database Tables & Seeding Data

Ensure your Docker PostgreSQL container is running (`.\start.ps1` or `docker compose up -d`), then initialize tables using one of the methods below:

#### Option A: Via Python Initialization Script (Recommended)
```bash
# Create all tables and models
python -m backend.init_db

# Or recreate with verified demo fixtures (Seller, Customer, Items, Categories, Requirements):
python -m backend.init_db --seed
```

#### Option B: Direct Execution via Docker PostgreSQL
```powershell
# On Windows (PowerShell):
Get-Content .\backend\schema.sql | docker compose exec -T db psql -U postgres -d hyperlocal_marketplace

# On Linux / macOS:
cat backend/schema.sql | docker compose exec -T db psql -U postgres -d hyperlocal_marketplace
```

#### Option C: Automated Setup Wizard
Running the replication wizard (`.\setup.ps1` or `./scripts/setup.sh`) automatically executes this schema initialization and verification suite as part of Step 8.

---

---

### 10. Seller Inventory Management System

The platform provides a high-throughput, multi-category catalog and inventory management engine for local merchants:

#### Database Architecture & Multi-Category Mapping
- Products are stored uniquely in `inventory_items` (ID, seller_id, product_name, price, is_available).
- Categories and sub-categories are stored uniquely in `categories` (category, sub_category).
- A many-to-many association table `item_categories` maps items to one or multiple categories (e.g., "Organic Farm Fresh Milk" mapped to both `Dairy` > `Milk & Cream` and `Organic` > `Fresh Dairy`) without duplicate product rows.

#### API Endpoints
- **Single Item Creation**:
  ```http
  POST /api/v1/items
  Content-Type: application/json

  {
    "seller_id": "e3b0c442-98fc-1c14-9afb-4c7ac2206123",
    "product_name": "Organic Whole Wheat Sourdough",
    "price": 85.0,
    "is_available": true,
    "category_names": ["Bakery", "Artisanal"]
  }
  ```
- **Bulk Item Upload (JSON)**:
  ```http
  POST /api/v1/items/bulk
  Content-Type: application/json

  {
    "seller_id": "e3b0c442-98fc-1c14-9afb-4c7ac2206123",
    "items": [
      {
        "product_name": "Pasteurized Cow Milk 500ml",
        "price": 32.0,
        "is_available": true,
        "category_names": ["Dairy", "Essentials"]
      },
      {
        "product_name": "Fresh Coriander Leaves 100g",
        "price": 15.0,
        "is_available": true,
        "category_names": ["Vegetables", "Herbs"]
      }
    ]
  }
  ```
- **Bulk Item Upload (CSV File)**:
  ```http
  POST /api/v1/items/upload-csv?seller_id=e3b0c442-98fc-1c14-9afb-4c7ac2206123
  Content-Type: multipart/form-data
  ```
  *(Accepts standard CSV with headers: `product_name,price,category,sub_category,is_available`)*
- **Real-Time Stock Availability Toggle**:
  ```http
  PATCH /api/v1/items/{item_id}/availability
  Content-Type: application/json

  {
    "is_available": false
  }
  ```
  *(Instantly boards or offboards items from customer discovery and geospatial matching without removing catalog history)*
- **Real-Time Price & Catalog Update**:
  ```http
  PUT /api/v1/items/{item_id}
  Content-Type: application/json

  {
    "price": 95.0,
    "is_available": true
  }
  ```

#### Seller Dashboard Catalog Management UI
- Switch between **📡 3 km Live Demand Radar** and **📦 Inventory & Catalog Management** tabs.
- Live catalog grid with real-time stock toggles, inline price editing, and category tags.
- Dedicated modals for **Add Single Item** (with category multi-select) and **Bulk Catalog Upload** (with curated 1-click merchant presets).

---

### 11. Order Acceptance & Escrow Payment Workflow

A complete end-to-end reverse-marketplace procurement loop protecting both customer and merchant:

```
[Customer Demand Broadcast]
           │
           ▼ (3 km PostGIS Spatial Radar)
[Local Merchants Notified]
           │
           ▼ (Itemized Quote Dispatched: Line Items, Delivery Window, Notes)
[Customer Portal Receives Quotes]
           │
           ▼ (Customer Reviews Itemized Bill & Clicks "Approve & Pay")
[Mock Escrow Settlement Gateway] ── (UPI / Card / Direct Escrow)
           │
           ▼
[Order Status -> FULFILLED]
[Requirement Status -> FULFILLED]
[Seller Completed Orders Counter Increments]
           │
           ▼ (Upon 2nd Completed Order)
[Freemium Billing Milestone Triggered] ── (Requires Rs. 1,000/mo platform fee)
```

#### Dedicated Vendor Quotation Endpoints
- **Submit Vendor Quotation**:
  ```http
  POST /quotations/submit
  Content-Type: application/json

  {
    "requirement_id": "<uuid>",
    "seller_id": "<uuid>",
    "itemized_prices": [
      { "product_name": "Pasteurized Milk 500ml", "quantity": "2 pkts", "unit_price": 35.0, "total": 70.0 },
      { "product_name": "Sourdough Bread 400g", "quantity": "1 loaf", "unit_price": 120.0, "total": 120.0 }
    ],
    "total_amount": 190.0,
    "estimated_delivery_time": "15-20 mins"
  }
  ```
  *(Enforces that the quoting seller has an active subscription; rejects with HTTP 403 Forbidden if trial expired and platform fee is unpaid)*

- **Retrieve Vendor Quotations for Requirement**:
  ```http
  GET /requirements/{requirement_id}/quotations
  ```
  *(Returns all vendor price quotes with seller contact details, itemized prices, total amount, delivery turnaround, and status)*

#### Order Fulfillment & Escrow Settlement Endpoints
- **Submit Itemized Quote & Create Order**:
  ```http
  POST /api/v1/orders/quote
  Content-Type: application/json

  {
    "requirement_id": "<uuid>",
    "seller_id": "<uuid>",
    "quote_amount": 145.0,
    "delivery_estimate_minutes": 20,
    "itemized_items": [
      { "item_name": "Pasteurized Cow Milk 500ml", "quantity": "2 pkts", "price": 32.0, "total": 64.0 },
      { "item_name": "Fresh Coriander Leaves 100g", "quantity": "1 bunch", "price": 15.0, "total": 15.0 }
    ],
    "notes": "Packed fresh from morning batch. Out for immediate delivery."
  }
  ```
- **Retrieve Quotes for Requirement (Customer)**:
  ```http
  GET /api/v1/orders/requirement/{requirement_id}
  ```
- **Approve & Settle Order via Escrow (Customer)**:
  ```http
  POST /api/v1/orders/{order_id}/pay
  Content-Type: application/json

  {
    "payment_method": "upi",
    "transaction_ref": "TXN_ESCROW_1729609200"
  }
  ```
  *Returns order settlement receipt, marks requirement fulfilled, updates seller order count, and flags freemium status.*

- **Seller Freemium Billing Status & Subscription**:
  ```http
  GET /api/v1/billing/seller/{seller_id}/status
  POST /api/v1/billing/seller/{seller_id}/pay
  ```

---

### 12. End-to-End Testing Guide

#### 1. Automated Integration Test Suite (CLI)
Run the comprehensive verification script covering all 8 phases of inventory management, bulk upload, real-time toggles, demand broadcast, quote dispatch, escrow payment, and freemium milestone triggers:

```bash
# Run against active FastAPI server:
.\.venv\Scripts\python.exe scratch/test_inventory_and_orders.py
```

Expected output:
```
[PASS] Phase 1: Created multi-category item (ID: ...)
[PASS] Phase 2: Bulk uploaded 3 items
[PASS] Phase 3: Toggled item availability to False
[PASS] Phase 4: Updated item price to Rs. 40.0
[PASS] Phase 5: Customer demand broadcast created (ID: ...)
[PASS] Phase 6: Seller submitted itemized quote (Order ID: ...)
[PASS] Phase 7: Customer approved & settled payment via Escrow!
[PASS] Phase 8: 2nd order completed -> Freemium milestone triggered ('pending_payment')
=== ALL 8 PHASES PASSED SUCCESSFULLY! ===
```

#### 2. Interactive Web UI Walkthrough (Browser)
1. Open `http://localhost:3000/`.
2. **Customer Portal**:
   - Type `"Need 2 packets of milk and fresh cilantro delivered quickly"`.
   - Click **Broadcast to Local Merchants**.
   - Review the AI structured shopping list and notified neighborhood stores.
   - Click **Simulate Instant Merchant Response** (or switch tabs to respond from the Seller Dashboard).
   - Inspect the itemized bill card with turnaround time and price breakdown.
   - Click **Approve & Pay ₹... (Escrow)**.
   - Select payment channel (UPI / Card / Direct Escrow) and click **Authorize & Pay**.
   - Verify the emerald **Payment Receipt** card displays with transaction reference and updated order status.
3. **Seller Dashboard**:
   - Switch to **Seller Dashboard** in the header.
   - Click **📦 Inventory & Catalog Management** sub-tab.
   - Toggle product availability between `In Stock` and `Offboarded` in real time.
   - Click **+ Add Item** to add a new product with multiple categories.
   - Click **Bulk Upload** to import pre-configured inventory catalogs in 1 click.
   - Switch to **📡 3 km Live Demand Radar** to monitor incoming customer broadcasts and track the Freemium Quota progress bar.

---

### 13. Pytest Integration Test Suite (`/backend/tests`)

A comprehensive, production-grade automated integration test suite engineered to simulate full user journeys and validate system error resilience:

#### Test Structure
- `backend/tests/conftest.py`: Shared pytest fixtures (`test_client`, `db_session`, `make_unique_phone`, `sample_location`).
- `backend/tests/test_e2e_user_journey.py`:
  1. Customer submits a natural language requirement with GPS coordinates.
  2. AI parser parses items, quantities, categories, and urgency.
  3. PostGIS `ST_DWithin` spatial query filters sellers strictly within 3 km radius while excluding distant sellers (e.g. 11.5 km away).
  4. Seller accepts order and submits itemized quote/bill.
  5. Customer approves and settles payment via Mock Escrow Gateway.
  6. Seller completed orders counter increments, triggering the freemium billing threshold (`pending_payment`, `can_receive_broadcasts = False`) upon the 2nd order.
  7. Seller pays platform fee (Rs. 1,000) to restore broadcast rights.
- `backend/tests/test_error_handling_and_edge_cases.py`:
  1. **LLM API Timeout Fallback**: External API timeouts gracefully fall back to the deterministic offline NLP rule parser without dropping customer requests.
  2. **Malformed JSON Handling**: Resilient parsing handles markdown fences (````json ... ````), conversational commentary, and trailing commas.
  3. **Blank / Whitespace Requirements**: Rejects empty inputs cleanly with 422 or returns safe zero-item schemas without 500 errors.
  4. **Geospatial Zero-Seller Handling**: Queries with no nearby merchants (e.g. remote coordinates) return HTTP 201 with empty lists and clear status messages (`no_sellers_within_radius`).
  5. **Coordinate Validation**: Out-of-bound WGS84 coordinates are rejected with 422.
  6. **Real-Time Offboarding**: Items with `is_available=False` are excluded from in-stock matching.

#### Running the Test Suite
```bash
# Using pytest directly:
.\.venv\Scripts\python.exe -m pytest backend/tests -v

# Or via Makefile:
make test
```

Expected output:
```text
backend/tests/test_e2e_user_journey.py::TestEndToEndUserJourney::test_full_user_journey_e2e PASSED [  9%]
backend/tests/test_error_handling_and_edge_cases.py::TestErrorHandlingAndEdgeCases::test_llm_api_timeout_fallback PASSED [ 18%]
backend/tests/test_error_handling_and_edge_cases.py::TestErrorHandlingAndEdgeCases::test_sanitize_and_parse_json_markdown_fence PASSED [ 27%]
backend/tests/test_error_handling_and_edge_cases.py::TestErrorHandlingAndEdgeCases::test_sanitize_and_parse_json_with_conversational_chatter PASSED [ 36%]
backend/tests/test_error_handling_and_edge_cases.py::TestErrorHandlingAndEdgeCases::test_sanitize_and_parse_json_trailing_commas PASSED [ 45%]
backend/tests/test_error_handling_and_edge_cases.py::TestErrorHandlingAndEdgeCases::test_sanitize_and_parse_json_completely_broken_fallback PASSED [ 54%]
backend/tests/test_error_handling_and_edge_cases.py::TestErrorHandlingAndEdgeCases::test_empty_and_whitespace_requirement_handling PASSED [ 63%]
backend/tests/test_error_handling_and_edge_cases.py::TestErrorHandlingAndEdgeCases::test_endpoint_empty_prompt_validation PASSED [ 72%]
backend/tests/test_error_handling_and_edge_cases.py::TestErrorHandlingAndEdgeCases::test_geospatial_zero_sellers_in_radius PASSED [ 81%]
backend/tests/test_error_handling_and_edge_cases.py::TestErrorHandlingAndEdgeCases::test_invalid_wgs84_coordinate_bounds PASSED [ 90%]
backend/tests/test_error_handling_and_edge_cases.py::TestErrorHandlingAndEdgeCases::test_offboarded_products_excluded_from_stock_match PASSED [100%]

============================= 11 passed in 1.03s ==============================
```

---

### 14. Single-Command Developer Orchestration (`run_dev`)

To streamline local development, a single orchestration command manages the entire stack:
1. Verifies Docker daemon and ensures the PostgreSQL PostGIS container is healthy.
2. Executes backend database migrations and table verification (`python -m backend.init_db`).
3. Launches the FastAPI backend on `http://localhost:8000` with hot reload.
4. Starts the Vite React web portal on `http://localhost:3000` concurrently.
5. Traps termination signals (`Ctrl+C`) to cleanly shut down all background processes.

#### On Windows (PowerShell):
```powershell
.\run_dev.ps1
```

#### On Linux / macOS / WSL:
```bash
./run_dev.sh
```

#### Via Makefile:
```bash
make dev      # Start complete stack
make test     # Run all pytest integration tests
make db-up    # Spin up Docker PostgreSQL
make db-down  # Stop Docker PostgreSQL
make mobile   # Start Expo mobile app
---

### 15. Order Acceptance & Status Tracking Lifecycle API

The platform implements an end-to-end order lifecycle managing requirements, quotations, customer acceptance, and delivery milestones:

| Lifecycle Stage | Status Value | Initiated By | Action & Side Effects |
|---|---|---|---|
| **Demand Broadcast** | `BROADCASTED` | Customer | Natural language requirement broadcasted to vendors within 3 km. |
| **Vendor Quoting** | `QUOTED` | Seller | Subscribed merchants submit itemized prices and delivery estimates via `/quotations/submit`. |
| **Quote Acceptance** | `ACCEPTED` | Customer | Customer calls `POST /orders/accept-quote`. Chosen quote marked `accepted`, competing quotes marked `rejected`, order & requirement set to `ACCEPTED`. |
| **Out for Delivery** | `OUT_FOR_DELIVERY` | Seller | Seller updates dispatch status via `PATCH /orders/{order_id}/status`. Requirement status synced. |
| **Fulfillment / Delivery** | `COMPLETED` | Seller | Order delivered. Sets `completed_at`, increments seller's `completed_orders_count`, triggers freemium 2-order milestone check. |
| **Cancellation** | `CANCELLED` | Customer / Seller | Order and requirement marked cancelled with audit notes. |

#### Key Endpoints:
```bash
# 1. Customer Accepts a Vendor Quote
curl -X POST http://localhost:8000/orders/accept-quote \
  -H "Content-Type: application/json" \
  -d '{
    "quotation_id": "b3f0980c-a991-4e41-b062-ee277889154a",
    "notes": "Please deliver to 2nd floor flat 204"
  }'

# 2. Seller Updates Delivery Status to OUT_FOR_DELIVERY
curl -X PATCH http://localhost:8000/orders/b3f0980c-a991-4e41-b062-ee277889154a/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "OUT_FOR_DELIVERY",
    "notes": "Rider picked up parcel and is on the way"
  }'

# 3. Seller Marks Order as COMPLETED
curl -X PATCH http://localhost:8000/orders/b3f0980c-a991-4e41-b062-ee277889154a/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "COMPLETED",
    "notes": "Package delivered to doorstep"
  }'
```

---

### 16. Rs. 1,000 Monthly Freemium Subscription Rule Enforcement

The platform enforces a strict freemium monetization model for merchants:

1. **Taxonomy & Order Tracking**:
   - Every seller has a `subscription_status` in `('trial', 'active', 'expired')`.
   - `completed_orders_count` (integer) tracks the total completed orders fulfilled by the merchant.
2. **Access Control Rule**:
   - If `completed_orders_count` > 2 and `subscription_status` != `'active'`, access is restricted (HTTP 403 Forbidden) whenever the merchant attempts to:
     - **View** incoming customer requirement broadcasts (`GET /requirements/nearby?seller_id={id}` or `GET /requirements/broadcasts/seller/{id}`).
     - **Respond** to customer demand broadcasts with a price quote (`POST /quotations/submit` or `POST /api/v1/orders/quote`).
   - The API returns an explicit error message:
     ```json
     {
       "detail": "Access restricted: Completed order count exceeds trial limit (completed_orders_count > 2) and subscription_status != 'active'. Please pay the Rs. 1,000 monthly platform fee payment to continue."
     }
     ```
3. **Unlocking Broadcast Access**:
   - Merchants pay the Rs. 1,000 monthly fee via `POST /api/v1/billing/seller/{seller_id}/pay`.
   - This transitions `subscription_status` to `'active'` (and `'subscribed'`), restoring full 30-day broadcast reception and quotation privileges regardless of order volume.

---

### 17. Live Order Delivery UI & Mobile Client Integration

The full order acceptance and status tracking lifecycle is integrated across the web and mobile interfaces:

1. **Seller Dashboard - Orders & Delivery Lifecycle Tab (`frontend-web`)**:
   - Dedicated **🛵 Orders & Delivery Lifecycle** tab displaying all store orders.
   - Live status filter pills (`ALL`, `ACCEPTED`, `OUT_FOR_DELIVERY`, `COMPLETED`, `PENDING`).
   - One-click workflow buttons:
     - `ACCEPTED` → `[🛵 Dispatch: Mark Out for Delivery]` (`OUT_FOR_DELIVERY`)
     - `OUT_FOR_DELIVERY` → `[✅ Mark Delivered & Complete Order]` (`COMPLETED`)
   - Transitioning to `COMPLETED` automatically updates completed order counters and refreshes the freemium billing quota in real time.
2. **Customer Portal - Live Delivery Stepper (`frontend-web`)**:
   - Interactive 3-step live delivery progress tracker (`✓ 1. Quote Accepted` → `🛵 2. On the Way` → `🎉 3. Delivered`).
   - Polling updates every 4 seconds to reflect dispatch and delivery events triggered by local merchants.
3. **Mobile Client Sync (`frontend-mobile`)**:
   - `src/api.js` updated with `getRequirementQuotes`, `acceptQuote`, `updateOrderStatus`, `getOrder`, and `getSellerOrders`.

---

### 18. Customer Requirement & Live 3 km Quotes View with Accept Quote Flow

A dedicated, real-time customer component (`CustomerRequirementQuotesView.jsx`) provides complete transparency from demand broadcast to order confirmation:

1. **Submitted Requirement Overview**:
   - Displays raw natural language prompt, AI structured shopping items (with item name, quantity, category, and units), urgency badge, GPS location coordinates, and 3 km radius coverage stats.
2. **Real-Time Incoming Quotes Feed**:
   - Automatically polls `/requirements/{requirement_id}/quotations` every 3.5 seconds for incoming vendor price offers.
   - Displays merchant name, estimated delivery time, phone number, itemized pricing breakdown table, total quote amount (₹), and status tag.
   - Includes a 1-click **"Simulate Seller Quote ⚡"** action button that submits a realistic quote from an eligible nearby seller for instant testing.
3. **Interactive "Accept Quote" Action**:
   - Green **"Accept Quote & Order 🚀"** button next to each vendor's price offer.
   - Calls `POST /orders/accept-quote` with the selected quote ID.
   - Transitions quote to `accepted`, marks competing quotes `rejected`, sets order and requirement status to `ACCEPTED`.
4. **Order Confirmation Screen & Live Delivery Stepper**:
   - Celebratory modal showing official Order ID, status badge (`ACCEPTED`), merchant contact info, estimated delivery time, and total bill.
   - Live 3-step doorstep delivery progress stepper (`✓ 1. Quote Accepted` → `🛵 2. On the Way` → `🎉 3. Delivered`) that polls updates in real time as the vendor marks the order out for delivery or completed.

---

## Common Operations


### Stop the Database (Preserve Data)
```bash
docker compose down
```
Data is safely stored in the `hyperlocal_postgres_data` Docker volume.

### Restart the Database
```bash
docker compose start
# or
docker compose up -d
```

### Reset Database (Wipe All Data)
```bash
docker compose down -v
docker compose up -d --build
```
> ⚠️ **Warning**: The `-v` flag deletes all volumes, wiping local development data and causing `01-init-extensions.sql` to execute fresh on the next startup.

### Backup & Restore

```bash
# Dump the database to a file on your host
docker compose exec -T db pg_dump -U postgres -d hyperlocal_marketplace > backup.sql

# Restore a dump file into the database
docker compose exec -T db psql -U postgres -d hyperlocal_marketplace < backup.sql
```

