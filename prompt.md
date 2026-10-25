# Hyperlocal Marketplace - Development Prompt Log & Rebuild Specification

This document contains:
1. **Chronological Prompt History**: All developer prompts submitted during the creation, hardening, and observability instrumentation of this database infrastructure.
2. **Quality & Engineering Improvements Log**: Key technical refinements applied (UTF-8 encoding fixes, PSScriptAnalyzer compliance, deep metrics monitoring).
3. **Master Rebuild Prompt**: A comprehensive, standalone prompt that can be provided to an AI agent in a fresh directory to rebuild this entire project from scratch.

---

## 1. Chronological Prompt History

### Phase 1: Container Setup & Initial Execution
#### Prompt 1: Initial Launch
> **User Prompt:**
> ```text
> start this docker
> ```
* **Action Taken:**
  - Inspected workspace (`Dockerfile`, `docker-compose.yml`, `.env.example`, `docker/init/01-init-extensions.sql`).
  - Verified Docker daemon connectivity and built the custom PostgreSQL 16 image with PostGIS 3 and pgvector.
  - Initialized the container and validated extensions (`postgis`, `vector`, `uuid-ossp`).

---

### Phase 2: Automation & Lifecycle Scripts
#### Prompt 2: Startup and Shutdown Scripting
> **User Prompt:**
> ```text
> Prepare this as two scripts and store in the workspace
> 1. First will do the startup activity and capture the generated startup logs along with the executed command in verbose mode in the file.
> 2. Second script will be for the shutdown activity 
> 
> We will extend the features of these scripts over the period.
> 
> Next time as an owner I will do the startup and shutdown with the help of scripts
> ```
* **Action Taken:**
  - Implemented `scripts/start.ps1` and `scripts/stop.ps1` with PowerShell root wrappers (`start.ps1`, `stop.ps1`).
  - Implemented cross-platform Bash scripts (`scripts/start.sh`, `scripts/stop.sh`).
  - Designed automated logging infrastructure writing verbose timestamped logs to `logs/startup_<timestamp>.log` and `logs/shutdown_<timestamp>.log`, mirrored to `logs/startup_latest.log` and `logs/shutdown_latest.log`.

---

### Phase 3: Replication, Factory Reset & Self-Healing
#### Prompt 3: Environment Setup & Machine Replication Wizard
> **User Prompt:**
> ```text
> you set up docker with mentioned details; I want that as a script in case if this current installation breaks/corrupt or if I want to replicate this same setup on another machine
> ```
* **Action Taken:**
  - Built `setup.ps1` and `scripts/setup.ps1` (+ `scripts/setup.sh`).
  - Implemented pre-flight checks, automatic `.env` generation from `.env.example`, image building, container health waiting, and an automated SQL verification test suite (testing PostGIS 3 km radius calculations using `ST_DWithin` and spatial indexing, vector cosine distances via pgvector, and UUID generation).
  - Added `-Repair`, `-ResetData`, and `-NoCache` flags for disaster recovery.

---

### Phase 4: Observability, Health Probes & Server Metrics
#### Prompt 4: Health Monitoring & Server Metrics
> **User Prompt:**
> ```text
> when starting or stopping the docker container using scripts; you captured logs; but can we see some commands in the scripts and their outputs showing started server; health monitoring; some importants server metrics which should be ideally checked
> ```
* **Action Taken:**
  - Enhanced `start.ps1` and `start.sh` with 3 core diagnostic categories:
    1. **Started Server Confirmation**: Port binding checks (`docker port`), process tree inspection (`docker top`).
    2. **Health Monitoring**: Docker health probe history (`docker inspect`), native PostgreSQL engine ping (`pg_isready`), extension version queries (`\dx`).
    3. **Important Server Metrics**: Live resource consumption (`docker stats --no-stream`: CPU %, Mem Usage, Net I/O, Block I/O, PIDs), container reliability (`RestartCount`, `OOMKilled`), volume disk space (`df -h /var/lib/postgresql/data`), database size, active queries, uptime, and buffer cache hit ratio (`cache_hit_pct`).
  - Enhanced `stop.ps1` with pre-shutdown active query safety inspection and post-shutdown volume preservation verification.
  - Built dedicated standalone diagnostic scripts: `health.ps1` / `scripts/health.ps1` and `scripts/health.sh` for on-demand metrics reporting to `logs/health_latest.log`.

---

### Phase 5: Linting, Static Analysis & Encoding Hardening
#### Prompt 5: PSScriptAnalyzer $null Comparison Rule
> **User Prompt:**
> ```text
> fix this error : [{
>     "resource": "/e:/hyperlocal-marketplace/scripts/start.ps1",
>     "owner": "_generated_diagnostic_collection_name_#3",
>     "code": "PSPossibleIncorrectComparisonWithNull",
>     "severity": 4,
>     "message": "$null should be on the left side of equality comparisons.",
>     "source": "PSScriptAnalyzer",
>     "startLineNumber": 107,
>     "startColumn": 29,
>     "endLineNumber": 107,
>     "endColumn": 48,
>     "origin": "extHost1"
> }]
> 
> I saw this is in other set of files as well
> ```
* **Action Taken:**
  - Identified `PSPossibleIncorrectComparisonWithNull` where `$ExitCode -eq $null` was flagged across `start.ps1`, `stop.ps1`, `setup.ps1`, and `health.ps1`.
  - Refactored condition to idiomatic PowerShell boolean negation: `if (-not $ExitCode)` across all four scripts, eliminating comparison with `$null` entirely.

#### Prompt 6 & Prompt 7: IDE Stale Diagnostic Verification
> **User Prompt:**
> ```text
> @[current_problems]
> @[health.ps1:current_problems]
> ```
* **Action Taken:**
  - Diagnosed Language Server in-memory caching behavior in VS Code / Antigravity IDE when background files are modified on disk.
  - Confirmed and demonstrated that re-saving or focusing tabs flushes Language Server diagnostic buffers.

#### Prompt 8: Windows PowerShell Output Encoding Corrupting Characters
> **User Prompt:**
> ```text
> @[e:\hyperlocal-marketplace\logs\health_latest.log] why such characters in the file
> ```
* **Action Taken:**
  - Diagnosed that `docker-entrypoint.sΓÇª` in line 11 of the log was caused by Windows PowerShell's default OEM Code Page (CP437) misinterpreting Docker's UTF-8 horizontal ellipsis (`…`, byte sequence `0xE2 0x80 0xA6`).
  - Added strict UTF-8 console output and pipe encoding to all PowerShell scripts:
    ```powershell
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
    ```
  - Re-executed `health.ps1` and verified clean rendering of `"docker-entrypoint.s…"`.

---

### Phase 6: FastAPI Backend Schema & Models
#### Prompt 9: Backend Core Database Schema, Models & Initialization
> **User Prompt:**
> ```text
> Act as a Senior Backend Architect. Our PostgreSQL database (with PostGIS and pgvector) is up and running via Docker. 
> 
> Now, let's build the core database schema and models for our Python FastAPI backend. Please create the following inside a new `/backend` folder:
> 
> 1. requirements.txt: List all necessary dependencies (e.g., fastapi, uvicorn, sqlalchemy, psycopg2-binary, pydantic, python-dotenv, geoalchemy2).
> 2. database.py: The SQLAlchemy connection engine setup using environment variables from a .env file.
> 3. models.py: SQLAlchemy models with the following tables:
>    - users: id, name, phone, role ('customer', 'seller', 'admin'), latitude, longitude (using PostGIS/GeoAlchemy2 for geospatial points), and created_at.
>    - inventory_items: id, seller_id (foreign key to users), product_name, category, sub_category, price, is_available (boolean toggle), and created_at. (Ensure a seller can map a product to multiple categories without duplicate core records).
>    - requirements: id, customer_id (foreign key to users), raw_text (natural language input), structured_json (parsed items), status, and created_at.
> 4. A quick initialization script or migration utility to create these tables in our Docker PostgreSQL instance.
> 5. Update the root README.md with instructions on how to install backend dependencies and initialize the database.
> 6. Incrementally enhance setup file with the activities you are performing for this stage
> ```
* **Action Taken:**
  - Designed normalized relational architecture in `backend/models.py` with `User`, `Category`, `InventoryItem`, `Requirement`, and `item_categories` association table for multi-category item mapping.
  - Added PostGIS geometry point column with GiST spatial indexing for sub-millisecond 3 km hyperlocal queries.
  - Implemented `backend/database.py` with SQLAlchemy connection pooling, automatic `.env` discovery, and FastAPI `get_db` session dependency.
  - Created `backend/requirements.txt` with FastAPI, SQLAlchemy 2, GeoAlchemy2, Shapely, pgvector, and psycopg2-binary.
  - Created `backend/init_db.py` CLI initialization and test data seeder utility.
  - Created `backend/schema.sql` and applied it to PostgreSQL container with verified sample data.
  - Enhanced `scripts/setup.ps1` and `scripts/setup.sh` to automatically apply the backend schema and verify table creations as Step 8 of replication.
  - Documented backend installation, virtualenv activation, and initialization in `README.md`.

---

### Phase 7: FastAPI Application Layer, Routers & Endpoints
#### Prompt 10: FastAPI Router and Endpoint Implementation
> **User Prompt:**
> ```text
> proceed with implementing FastAPI router and endpoint
> ```
* **Action Taken:**
  - Implemented `backend/schemas.py`: Comprehensive Pydantic v2 validation DTOs and response serializers (`UserCreate`, `UserResponse`, `CategoryCreate`, `InventoryItemCreate`, `NearbyItemsResponse`, `RequirementCreate`, etc.).
  - Implemented `backend/crud.py`: Robust business logic and PostGIS spherical distance calculations using `func.ST_DWithin` and `func.ST_Distance` on `geography(location)`.
  - Fixed SQLEnum string mapping in `backend/models.py` with `values_callable=lambda x: [e.value for e in x]` ensuring clean enum deserialization.
  - Built modular sub-routers under `backend/routers/`:
    - `health.py`: `GET /health` deep diagnostic probe verifying database connectivity, PostgreSQL 16, PostGIS 3.6, pgvector 0.8, and table counts; `GET /` service metadata.
    - `users.py`: `POST /api/v1/users`, `GET /api/v1/users`, `GET /api/v1/users/{id}`, `PUT /api/v1/users/{id}`, `DELETE /api/v1/users/{id}` with automatic PostGIS `POINT(lon, lat)` spatial sync.
    - `categories.py`: `POST /api/v1/categories`, `GET /api/v1/categories`, `GET /api/v1/categories/{id}` taxonomy management.
    - `inventory.py`: `POST /api/v1/items`, `GET /api/v1/items/nearby` (hyperlocal PostGIS radius query sorting by geodesic distance), `GET /api/v1/items/seller/{id}`, `PATCH /api/v1/items/{id}/availability`.
    - `requirements.py`: `POST /api/v1/requirements` (natural language customer demand), `GET /api/v1/requirements/nearby` (merchant discovery within radius), `PATCH /api/v1/requirements/{id}/status`.
  - Implemented `backend/main.py`: FastAPI app instance with CORS middleware, lifespan events, and global exception handlers.
  - Implemented `backend/test_api.py`: Automated end-to-end integration test suite validating all endpoints against live Docker PostgreSQL.
  - Updated `README.md` with complete endpoint reference, local server execution commands, and test documentation.

---

### Phase 8: AI Parser & 3 km Geospatial Matching Engine
#### Prompt 11: AI Requirement Parsing and 3 km PostGIS Matching Engine
> **User Prompt:**
> ```text
> Act as an AI and Geospatial Backend Engineer. Now that our FastAPI routers are set up, let's implement the core AI parsing and 3 km matching engine inside /backend:
> 
> 1. ai_parser.py:
>    - Implement an async function using an LLM client (support OpenAI, Anthropic, or Gemini via API key) that takes raw customer requirement text.
>    - Use Pydantic structured outputs / JSON mode to guarantee a strict response format containing: items (list of product name, quantity, category), urgency, and additional notes.
> 
> 2. matching_engine.py:
>    - Write a geospatial matching service using SQLAlchemy and GeoAlchemy2 / PostGIS.
>    - Given a customer's latitude and longitude, query the users table to find all active sellers whose location falls strictly within a 3 km radius (ST_DWithin).
>    - Filter those sellers against the items in the parsed shopping list to see who matches the inventory categories/products.
> 
> 3. endpoints/requirements.py (or main router):
>    - Create a POST /requirements/submit endpoint that accepts the raw text and customer GPS coordinates, triggers the AI parser, saves the requirement to the database, runs the 3 km geospatial seller search, and returns the parsed summary along with the count of notified local sellers.
> 
> 4. Add the required API key variables (e.g., OPENAI_API_KEY or GEMINI_API_KEY) to .env.example.
> ```
* **Action Taken:**
  - Implemented `backend/ai_parser.py`: Multi-provider async parser supporting Google Gemini (`gemini-1.5-flash`), OpenAI (`gpt-4o-mini`), and Anthropic (`claude-3-5-haiku-latest`) via REST endpoints using `httpx.AsyncClient` with Pydantic structured outputs (`ParsedRequirement`, `ParsedItem`, `UrgencyLevel`). Included an intelligent deterministic offline rule fallback so local development and integration tests run reliably with zero external API dependencies.
  - Implemented `backend/matching_engine.py`: High-performance geospatial matching service using PostGIS `ST_DWithin` and spherical `ST_Distance` on WGS84 coordinates. Evaluates nearby sellers' active inventory items against requested items via exact/partial string matching and category taxonomy overlap. Ranks merchants by fulfillment percentage and proximity.
  - Implemented `POST /requirements/submit` (and versioned alias `/api/v1/requirements/submit`): Seamlessly provisions customer coordinates, triggers AI parsing, persists requirements into PostgreSQL with JSONB structured output, executes 3 km spatial matching, and returns notified seller metrics.
  - Added `LLM_PROVIDER`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, and `ANTHROPIC_API_KEY` to `.env.example` and `.env`.
  - Added `test_06_ai_parsing_and_3km_matching` to `backend/test_api.py` and verified all tests pass cleanly.

---

### Phase 9: Frontend Web Interfaces (React, Tailwind CSS & Vite)
#### Prompt 12: Customer Portal & Seller Dashboard Interfaces
> **User Prompt:**
> ```text
> Act as a Full-Stack Web Developer. Now that our FastAPI backend with the AI parser and 3 km geospatial matching engine is complete, let's build the frontend interfaces inside a `/frontend-web` folder using React (Next.js or Vite) and Tailwind CSS:
> 
> 1. Project Setup:
>    - Initialize a clean React + Tailwind CSS project in `/frontend-web`.
>    - Configure an API service client (using Axios or Fetch) to communicate with our FastAPI backend running at `http://localhost:8000`.
> 
> 2. Customer Portal View:
>    - Create a clean, minimalist landing page with a prominent, large natural language text box (e.g., "What do you need today? Type anything...").
>    - Add input fields for customer GPS coordinates (or a mock location pin for Wakad, Pune).
>    - On submit, call the backend `/requirements/submit` endpoint and display the AI-generated structured shopping list summary along with confirmation of how many local sellers within 3 km were notified.
> 
> 3. Seller Dashboard View:
>    - Create a separate dashboard view for local sellers.
>    - Display a live feed of incoming customer requirement broadcasts matching their 3 km zone.
>    - Add an interactive "Accept Order & Quote Price" action button for sellers.
> 
> 4. Update root README.md with clear step-by-step instructions on how to concurrently launch the FastAPI backend and the React frontend.
> ```
* **Action Taken:**
  - Initialized high-performance React + Tailwind CSS v4 project via Vite inside `frontend-web/`.
  - Implemented `frontend-web/src/api/client.js`: Robust API client communicating with FastAPI backend at `http://localhost:8000`.
  - Built `frontend-web/src/components/Header.jsx`: Glassmorphic navigation header featuring real-time PostgreSQL 16 + PostGIS live health check ping and seamless view switching.
  - Built `frontend-web/src/components/CustomerPortal.jsx`:
    - Prominent natural language input with suggested prompts.
    - Quick location presets (Wakad, Pune: 18.5987, 73.7660; Indiranagar, Bangalore: 12.9745, 77.6350) + HTML5 Geolocation API.
    - Post-submit view displaying notification confirmation banner, AI-structured shopping list card with extracted items and urgency, and interactive cards for notified merchants within 3 km with live distance tags and in-stock items.
  - Built `frontend-web/src/components/SellerDashboard.jsx`:
    - Live 3 km radar feed auto-refreshing incoming customer demand broadcasts within the merchant's 3 km perimeter.
    - Interactive "Accept Order & Quote Price" modal allowing merchants to input custom price quotes (₹), delivery time estimates, and fulfillment notes, with instant status synchronization.
  - Verified end-to-end functionality in a browser subagent session.
  - Updated `README.md` with step-by-step concurrent launch instructions for backend and frontend.

---

### Phase 10: Freemium Billing Lifecycle & Expo Mobile App Scaffolding
#### Prompt 13: Freemium Business Logic, Order Quota Checks & Expo Mobile Interface
> **User Prompt:**
> ```text
> Act as a Full-Stack Product Architect. Let's expand our hyperlocal reverse-marketplace by implementing the freemium billing lifecycle and setting up the mobile interface framework:
> 
> 1. Freemium Business Logic & Tracking:
>    - Add backend models/logic to track completed orders per seller.
>    - Implement an automated check: after a seller completes their 2nd successful order, trigger a subscription status update to 'trial_expired' or 'pending_payment', requiring the Rs. 1,000 monthly platform fee to continue receiving broadcasts.
>    - Create a basic payment/subscription status endpoint for sellers.
> 
> 2. Mobile App Scaffolding (React Native / Expo):
>    - Initialize a new `/frontend-mobile` folder using Expo (React Native) supporting both Android and iOS.
>    - Build a clean mobile customer interface featuring the natural language requirement text box, location selector, and AI shopping list summary view.
>    - Ensure the mobile client connects seamlessly to our FastAPI backend endpoints.
> 
> 3. Update Documentation:
>    - Update the root `README.md` with instructions on how to test the seller order count trigger and how to run the Expo mobile app locally.
> ```
* **Action Taken:**
  - **Database Migration & Models (`backend/models.py`, `backend/schema.sql`)**:
    - Added `SubscriptionStatus` (`active_trial`, `pending_payment`, `trial_expired`, `subscribed`) and `OrderStatus` (`pending`, `accepted`, `completed`, `cancelled`) enums.
    - Updated `User` model with `subscription_status`, `completed_orders_count`, `free_orders_remaining`, `subscription_expires_at`, and `can_receive_broadcasts` property.
    - Created `Order` model tracking fulfilled demands, seller quotes, and timestamps.
    - Successfully migrated live PostgreSQL 16 container with `orders` table and column additions.
  - **Backend Freemium & Billing Logic (`backend/crud.py`, `backend/routers/billing.py`)**:
    - `POST /api/v1/orders/complete`: Increments completed orders, decrements free quota, and triggers automated check: upon reaching the 2nd completed order in `active_trial`, status transitions to `pending_payment`, setting `can_receive_broadcasts = False` and raising `trial_expired_alert = True`.
    - `GET /api/v1/billing/seller/{seller_id}/status`: Returns seller subscription quota, expiry, and human-readable billing status.
    - `POST /api/v1/billing/seller/{seller_id}/pay`: Processes Rs. 1,000 monthly platform fee, transitioning seller to `subscribed` for 30 days and restoring broadcast alerts.
    - `backend/matching_engine.py`: Updated to gate broadcast notifications (`notified_sellers_count`) strictly to sellers with `can_receive_broadcasts = True`.
  - **Automated Freemium Test Suite (`scratch/test_freemium_billing.py`)**:
    - Complete test verifying: Order 1 (1 trial remaining) -> Order 2 (automated lock to `pending_payment` & broadcast gate) -> Matching exclusion -> Platform fee payment (Rs. 1,000) -> Status restored to `subscribed`.
  - **Mobile App Scaffolding (`/frontend-mobile`)**:
    - Scaffolded Expo React Native app supporting Android, iOS, and Web.
    - Built comprehensive customer interface in `App.js`: natural language requirement textarea with quick-fill prompts, location chip selector (Wakad, Indiranagar, Custom GPS), AI structured shopping list cards with urgency badges, 3 km nearby merchant cards with in-stock matches, and configurable backend API URL modal.
    - Implemented `src/api.js` and `src/config.js` connecting to FastAPI backend with emulator/device host routing.
  - **Documentation**:
    - Updated root `README.md` with complete instructions for running the automated freemium trigger test and launching the Expo mobile app across platforms.

---

### Phase 11: Seller Inventory Management System & Order Acceptance / Payment Loop
#### Prompt 14: Inventory Management API & UI, Multi-Category Product Mapping, Quote Dispatch & Mock Escrow Settlement
> **User Prompt:**
> ```text
> Act as a Full-Stack Systems Architect. Let's build out the Seller Inventory Management system and the final order acceptance/payment loop:
> 
> 1. Seller Inventory Management API & UI:
>    - Create robust backend endpoints for sellers to bulk-upload or add individual inventory items.
>    - Ensure the database schema allows a single product record to be associated with multiple categories/sub-categories without duplication.
>    - Implement toggle controls allowing sellers to easily board/offboard products or adjust pricing in real time.
>    - Build a matching UI component in the seller dashboard so vendors can manage their catalog effortlessly.
> 
> 2. Order Acceptance & Payment Workflow:
>    - Implement the workflow where a seller accepts an incoming requirement and submits a final itemized quote/bill.
>    - Create a mock payment gateway integration or escrow settlement handler for the customer to approve and pay the order.
>    - Ensure successful order completion correctly increments the seller's completed order counter to trigger the freemium billing milestone.
> 
> 3. Documentation:
>    - Update the root `README.md` to document the inventory management workflows and how to test the complete end-to-end customer-to-seller-to-payment cycle.
> ```
* **Action Taken:**
  - **Database Architecture & Multi-Category Deduplication (`backend/models.py`, `backend/schema.sql`)**:
    - Enhanced schema with `item_categories` many-to-many association table, allowing a single `inventory_items` row to map to multiple `categories` without duplicate product entries.
    - Added `itemized_quote JSONB` column to `orders` table to persist line-item breakdowns, quantities, and pricing.
  - **Backend Inventory & Bulk Upload Endpoints (`backend/routers/inventory.py`, `backend/crud.py`)**:
    - `POST /api/v1/items`: Single item creation with automatic `get_or_create_category` multi-category mapping.
    - `POST /api/v1/items/bulk`: Bulk JSON upload endpoint for batch inventory creation.
    - `POST /api/v1/items/upload-csv`: Multi-part CSV file upload parsing CSV rows into catalog items. Installed `python-multipart`.
    - `PATCH /api/v1/items/{item_id}/availability`: Real-time stock toggle (`is_available: true/false`) to board/offboard items without deleting history.
    - `PUT /api/v1/items/{item_id}`: Real-time price and product detail updates.
  - **Order Acceptance & Escrow Payment Workflow (`backend/routers/billing.py`, `backend/crud.py`)**:
    - `POST /api/v1/orders/quote`: Seller accepts requirement, submits total amount, delivery turnaround minutes, notes, and itemized line items list, creating `Order` in `PENDING` status.
    - `GET /api/v1/orders/requirement/{requirement_id}`: Customer queries/polls incoming merchant quotes.
    - `POST /api/v1/orders/{order_id}/pay`: Mock Escrow settlement handler: customer authorizes payment (UPI / Card / Direct Escrow). Settle handler transitions order to `FULFILLED`, marks requirement `FULFILLED`, generates transaction reference ID, increments seller completed order counter, and triggers freemium milestone upon 2nd order.
  - **Frontend Web UI (`frontend-web/src/components/`)**:
    - `SellerDashboard.jsx`: Added dual sub-tab navigation (`📡 3 km Live Demand Radar` vs `📦 Inventory & Catalog Management`), real-time stock toggle buttons, inline price editing, product deletion, single-item addition modal with category selection, and bulk upload modal with 1-click curated presets.
    - `CustomerPortal.jsx`: Added incoming quotes polling, itemized bill display cards, "Simulate Merchant Response" quick-test action, and interactive "Mock Escrow Checkout Modal" with payment channel selection (UPI / Card / Direct Escrow) and instant settlement receipt banner.
  - **Automated Verification & Browser Recording**:
    - Built and executed `scratch/test_inventory_and_orders.py` (100% pass across all 8 phases).
    - Executed browser subagent session validating the complete end-to-end customer broadcast -> merchant quote -> mock escrow payment -> inventory catalog management loop.
  - **Documentation**:
    - Updated `README.md` and `prompt.md` with complete API specifications and testing guides.

---

### Phase 12: Quality Assurance, Integration Testing & Developer Orchestration
#### Prompt 15: Pytest Integration Test Suite, LLM Fallbacks, Geospatial Edge Cases & run_dev Orchestrator
> **User Prompt:**
> ```text
> Act as a Principal QA and Systems Integration Engineer. Now that our core components (AI parser, 3 km geospatial matching, inventory management, and freemium billing) are built, let's write comprehensive integration tests and harden the application flow:
> 
> 1. End-to-End Integration Tests (/backend/tests):
>    - Write pytest test cases simulating the full user journey:
>      a. Customer submits a natural language requirement with GPS coordinates.
>      b. AI parser successfully converts it to a structured JSON shopping list.
>      c. PostGIS spatial query correctly filters sellers within the 3 km radius.
>      d. Seller accepts the order, increments the successful order counter, and tests the freemium billing threshold trigger.
> 
> 2. Error Handling & Edge Cases:
>    - Add robust fallback mechanisms for LLM API timeouts or malformed JSON responses.
>    - Ensure graceful error handling for geospatial queries when no sellers are found within the 3 km radius.
> 
> 3. Developer Convenience Script:
>    - Create a single orchestration script (run_dev.sh or Makefile) to spin up Docker PostgreSQL, run backend migrations, launch the FastAPI server, and start the frontend web/mobile interfaces concurrently.
> ```
* **Action Taken:**
  - **Pytest Integration Test Suite (`/backend/tests`)**:
    - Installed `pytest>=8.0.0` and `pytest-asyncio>=0.23.0`, updating `backend/requirements.txt` and `pytest.ini`.
    - `backend/tests/conftest.py`: Built shared fixtures (`test_client`, `db_session`, `make_unique_phone`, `sample_location`).
    - `backend/tests/test_e2e_user_journey.py`: Built full user journey test: Customer demand submission -> AI parsing validation -> PostGIS 3 km radius filtering (verifying inclusion of 650m seller and strict spatial exclusion of 11.5 km distant seller) -> Seller itemized quote submission -> Customer Mock Escrow payment -> Counter increment -> 2nd order freemium threshold trigger (`pending_payment`, `can_receive_broadcasts = False`) -> Platform fee settlement (Rs. 1,000) unlocking broadcast rights.
    - `backend/tests/test_error_handling_and_edge_cases.py`: Built 6 resilience test cases:
      1. LLM API timeout simulation gracefully falling back to deterministic offline NLP rule parser.
      2. Resilient JSON sanitization (`_sanitize_and_parse_json`) handling markdown fences, conversational commentary, and trailing commas.
      3. Blank / whitespace input validation.
      4. Geospatial queries with zero nearby sellers returning HTTP 201 with empty lists and clear status messages (`no_sellers_within_radius`).
      5. WGS84 coordinate boundary validation (rejecting lat/lon outside [-90, 90] / [-180, 180]).
      6. Exclusion of offboarded products (`is_available = False`) from in-stock matching.
  - **Hardened Application Flow (`backend/ai_parser.py`, `backend/matching_engine.py`)**:
    - Added `_sanitize_and_parse_json` with regex trailing comma cleanup and markdown fence stripping.
    - Configured explicit `LLM_TIMEOUT_SECONDS` (10s) with `httpx.Timeout(connect=5.0)`.
    - Added empty/whitespace input handling in `parse_requirement_text`.
    - Added `coverage_status` (`active_sellers_found` / `no_sellers_within_radius`) and user-friendly `status_message` in `GeospatialMatchSummary`.
  - **Developer Convenience Orchestration Scripts**:
    - Built `run_dev.ps1` for Windows PowerShell.
    - Built `run_dev.sh` (POSIX Bash) for Linux/macOS/WSL.
    - Built `Makefile` (`make dev`, `make test`, `make db-up`, `make db-down`, `make db-init`, `make clean`).
  - **Test Execution**:
    - Ran `pytest backend/tests -v` with 11/11 tests passing in ~1.0 second.
  - **Documentation**:
    - Updated `README.md` with Section 13 (Pytest Test Suite) and Section 14 (run_dev Developer Orchestration).

---

### Phase 13: Vendor Quotation Feature & Customer Quote Viewing Endpoints
#### Prompt 16: Quotations SQLAlchemy Model, POST /quotations/submit & GET /requirements/{id}/quotations
> **User Prompt:**
> ```text
> Act as a Backend Developer. Let's add the vendor quotation feature to our FastAPI backend:
> 1. Create a new SQLAlchemy model quotations in models.py with fields: id, requirement_id (foreign key), seller_id (foreign key), itemized_prices (JSON), total_amount, estimated_delivery_time, and status ('pending', 'accepted', 'rejected').
> 2. Create a POST endpoint /quotations/submit where a subscribed seller can submit a price quote for a specific customer requirement.
> 3. Create a GET endpoint /requirements/{requirement_id}/quotations for customers to view all quotes submitted by local sellers.
> ```
* **Action Taken:**
  - **SQLAlchemy ORM Model & Migration (`backend/models.py`, `backend/schema.sql`)**:
    - Created `QuotationStatus` enum (`pending`, `accepted`, `rejected`).
    - Created `Quotation` model mapping to table `quotations` with fields: `id` (UUID PK), `requirement_id` (FK to requirements.id), `seller_id` (FK to users.id), `itemized_prices` (JSONB), `total_amount` (Numeric(10,2)), `estimated_delivery_time` (String(100)), and `status` (`quotation_status_enum`).
    - Added bi-directional relationships with cascade delete to `User` and `Requirement`.
    - Executed table creation against PostgreSQL 16 container, verified with `init_db`.
  - **Pydantic Schemas (`backend/schemas.py`)**:
    - `QuotationSubmitRequest`: Validates requirement_id, seller_id, itemized_prices, total_amount (> 0), and estimated_delivery_time.
    - `QuotationResponse`: Complete serialized quotation representation with nested `seller` summary.
  - **CRUD & Subscription Enforcement (`backend/crud.py`)**:
    - `create_quotation`: Verifies seller and requirement exist; enforces that seller has role `seller` and has an active subscription (`can_receive_broadcasts` and not `pending_payment` / `trial_expired`). Rejects unauthorized submissions with `HTTP 403 Forbidden`.
    - `list_quotations_for_requirement`: Retrieves all quotes for a customer requirement ordered by `created_at DESC` with joined seller details.
  - **FastAPI Endpoints (`backend/routers/quotations.py`, `backend/main.py`)**:
    - `POST /quotations/submit` (and `/api/v1/quotations/submit`): Subscribed seller quote submission.
    - `GET /requirements/{requirement_id}/quotations` (and `/api/v1/requirements/{requirement_id}/quotations`): Customer quote viewing.
    - Registered `quotations.router` in `backend/main.py`.
  - **Integration Tests (`backend/tests/test_quotations.py`)**:
    - Tested successful quote submission by subscribed/trial seller.
    - Tested rejection (HTTP 403) for sellers with expired trial before paying platform fee.
    - Tested retrieval of quotes by customer with seller details.
    - Tested 404 validation for nonexistent requirements or sellers.
    - All 14 test cases in `backend/tests` passing in 1.44s.

---

### Phase 14: Order Acceptance & Status Tracking Lifecycle
#### Prompt 17: Order Acceptance (POST /orders/accept-quote) & Status Tracking (PATCH /orders/{order_id}/status)
> **User Prompt:**
> ```text
> Act as a Backend Developer. Now let's implement the order acceptance and status tracking lifecycle:
> 1. Create a new SQLAlchemy model `orders` or update `requirements` to include an order lifecycle status: 'BROADCASTED', 'QUOTED', 'ACCEPTED', 'OUT_FOR_DELIVERY', 'COMPLETED', and 'CANCELLED'.
> 2. Create a POST endpoint `/orders/accept-quote` where a customer selects a specific seller's quote, transitioning the order status to 'ACCEPTED'.
> 3. Create a PATCH endpoint `/orders/{order_id}/status` allowing the seller to update the delivery status (e.g., to 'OUT_FOR_DELIVERY' or 'COMPLETED').
> ```
* **Action Taken:**
  - **SQLAlchemy ORM Model & Database Lifecycle Status (`backend/models.py`, `backend/schema.sql`)**:
    - Updated `OrderStatus` and `RequirementStatus` enums and models with lifecycle status values: `'BROADCASTED'`, `'QUOTED'`, `'ACCEPTED'`, `'OUT_FOR_DELIVERY'`, `'COMPLETED'`, and `'CANCELLED'` (retaining backward compatibility aliases).
    - Updated `orders.status` and `requirements.status` columns in PostgreSQL to `VARCHAR(50)` for schema flexibility.
    - Updated `Order` model with `quotation_id` (FK to `quotations.id` on delete `SET NULL`) and `relationship("Quotation")`.
  - **Pydantic Schemas (`backend/schemas.py`)**:
    - `OrderAcceptQuoteRequest`: Validates `quotation_id` (UUID) and customer `notes`.
    - `OrderStatusUpdateRequest`: Validates `status` (string) and optional `notes`.
    - `OrderResponse`: Added `quotation_id: Optional[UUID] = None` and `status: Union[OrderStatus, str]`.
  - **CRUD Operations (`backend/crud.py`)**:
    - `get_order`: Retrieves order by UUID with preloaded relationships (`seller`, `customer`, `quotation`, `requirement`).
    - `accept_quotation_and_create_order`: Transitions selected quote to `'accepted'`, competing quotes for requirement to `'rejected'`, linked requirement to `'ACCEPTED'`, and creates/transitions `Order` in `'ACCEPTED'` status.
    - `update_order_delivery_status`: Validates status in `{'BROADCASTED', 'QUOTED', 'ACCEPTED', 'OUT_FOR_DELIVERY', 'COMPLETED', 'CANCELLED'}`. Syncs linked requirement status. If status is `'COMPLETED'`, marks `completed_at`, increments seller's `completed_orders_count`, decrements `free_orders_remaining`, and triggers freemium milestone to `'pending_payment'` after 2nd order.
  - **FastAPI Endpoints (`backend/routers/orders.py`, `backend/main.py`)**:
    - `POST /orders/accept-quote` (and `/api/v1/orders/accept-quote`): Customer accepts quote.
    - `PATCH /orders/{order_id}/status` (and `/api/v1/orders/{order_id}/status`): Seller updates delivery status.
    - `GET /orders/{order_id}` (and `/api/v1/orders/{order_id}`): Inspect order details.
    - Registered `orders.router` in `backend/main.py`.
  - **Integration Tests (`backend/tests/test_order_lifecycle.py`)**:
    - Full lifecycle test: quote acceptance -> competing quotes rejected -> requirement & order 'ACCEPTED' -> seller status update to 'OUT_FOR_DELIVERY' -> seller status update to 'COMPLETED' with timestamp and seller order counter increment.
    - Order cancellation lifecycle test ('CANCELLED').
    - Status validation test (400 Bad Request on invalid status).
    - 404 handling for nonexistent quotation or order.
    - Alias routes (`/api/v1/...`) verification.
    - All 20 test cases passing cleanly across the test suite.

---

### Phase 15: Rs. 1,000 Monthly Freemium Subscription Rule Enforcement
#### Prompt 18: Freemium Subscription Status ('trial', 'active', 'expired') & Broadcast Gating
> **User Prompt:**
> ```text
> Act as a Backend Developer. Let's enforce the Rs. 1,000 monthly freemium subscription rule:
> 1. Add a `subscription_status` field ('trial', 'active', 'expired') and a `completed_orders_count` integer to the seller user model.
> 2. Write a helper function or middleware that checks a seller's completed order count when they attempt to view or respond to new requirement broadcasts.
> 3. If `completed_orders_count` > 2 and `subscription_status` != 'active', restrict their access and return a message requiring the Rs. 1,000 monthly platform fee payment to continue.
> ```
* **Action Taken:**
  - **Seller Model & Status Taxonomy (`backend/models.py`, `backend/schema.sql`)**:
    - Updated `SubscriptionStatus` enum to include `'trial'`, `'active'`, and `'expired'` (with backward compatibility aliases).
    - `User.subscription_status` defaults to `'trial'`.
    - `User.completed_orders_count` tracks total fulfilled orders.
    - Updated `User.can_receive_broadcasts` to restrict sellers when `completed_orders_count > 2` and status is not `'active'`.
  - **Subscription Enforcement Helpers & Middleware (`backend/subscription.py`)**:
    - `check_seller_subscription_access(seller)`: Evaluates eligibility. If `completed_orders_count > 2 and subscription_status != 'active'`, returns `(False, "Access restricted: Completed order count exceeds trial limit (completed_orders_count > 2) and subscription_status != 'active'. Please pay the Rs. 1,000 monthly platform fee payment to continue.")`.
    - `enforce_seller_broadcast_access(seller_or_id, db)`: Helper function raising `HTTPException(403)` when access is restricted.
    - `require_seller_broadcast_access`: FastAPI dependency for router parameter injection.
  - **Broadcast Viewing & Quoting Gating (`backend/routers/requirements.py`, `backend/routers/quotations.py`, `backend/routers/billing.py`)**:
    - `GET /requirements/nearby` and `GET /api/v1/requirements/nearby`: Added `seller_id` query parameter; invokes `enforce_seller_broadcast_access`.
    - `GET /requirements/broadcasts/seller/{seller_id}`: Dedicated merchant broadcasts feed enforcing the freemium rule.
    - `POST /quotations/submit` & `POST /api/v1/orders/quote`: Enforces subscription rule before allowing a merchant to respond to broadcasts.
  - **Integration & Unit Tests (`backend/tests/test_freemium_subscription.py`)**:
    - Unit tests for `check_seller_subscription_access` across all lifecycle states.
    - Test viewing broadcasts restricted when `completed_orders_count > 2` and status != `'active'` (HTTP 403 with Rs. 1,000 fee message).
    - Test responding to broadcasts restricted when `completed_orders_count > 2` and status != `'active'`.
    - Test access immediately restored upon paying Rs. 1,000 platform fee.
    - All 24 tests in `backend/tests` passing with 100% pass rate.

* **Phase 16: Interactive Order Delivery Lifecycle UI, Live Customer Stepper & Mobile Client Integration**:
  - **Seller Dashboard UI (`frontend-web/src/components/SellerDashboard.jsx`)**:
    - Added third dedicated tab: `🛵 Orders & Delivery Lifecycle ({orders.length})` and 5-column dashboard summary stats.
    - Added status filter pills (`ALL`, `ACCEPTED`, `OUT_FOR_DELIVERY`, `COMPLETED`, `PENDING`).
    - Added real-time order lifecycle transition controls:
      - `ACCEPTED` → `[🛵 Dispatch: Mark Out for Delivery]` (`OUT_FOR_DELIVERY`)
      - `OUT_FOR_DELIVERY` → `[✅ Mark Delivered & Complete Order]` (`COMPLETED`)
    - Automatically updates completed order counters and refreshes freemium billing quota on fulfillment.
  - **Customer Portal UI (`frontend-web/src/components/CustomerPortal.jsx`)**:
    - Added live 3-step delivery progress stepper (`✓ 1. Quote Accepted` → `🛵 2. On the Way` → `🎉 3. Delivered`).
    - Periodic polling updates reflecting live status transitions triggered by merchants.
  - **Mobile Client Sync (`frontend-mobile/src/api.js`)**:
    - Added `getRequirementQuotes`, `acceptQuote`, `updateOrderStatus`, `getOrder`, and `getSellerOrders`.
  - **Backend Route Aliasing (`backend/routers/billing.py`)**:
    - Added root route alias `GET /orders/seller/{seller_id}` alongside `/api/v1/orders/seller/{seller_id}`.

---

### Phase 17: Customer Requirement Live 3 km Quotes View & Accept Quote Flow
#### Prompt 19: Dedicated Customer Requirement & Live Quotes Component with Accept Quote Confirmation
> **User Prompt:**
> ```text
> Act as a Frontend Developer. Let's update our React web frontend:
> 1. Create a component where a customer can view their submitted requirement and see a live list of incoming price quotes submitted by local sellers within 3 km.
> 2. Add an "Accept Quote" button next to each vendor's price offer that triggers the `/orders/accept-quote` API and displays a confirmation screen.
> ```
* **Action Taken:**
  - **Customer Requirement & Quotes Component (`frontend-web/src/components/CustomerRequirementQuotesView.jsx`)**:
    - Built dedicated responsive component rendering the submitted requirement summary: raw natural language prompt, AI parsed shopping items with categories & units, urgency badge, broadcast GPS coordinates (lat/lng), and 3 km coverage perimeter stats.
    - Implemented real-time polling feed querying `/requirements/{id}/quotations` and `/api/v1/orders/requirement/{id}` every 3.5 seconds.
    - Rendered incoming vendor quote cards featuring merchant business name, delivery turnaround estimate, contact phone number, itemized pricing breakdown table, total quote amount (₹), and live status badge.
    - Integrated a 1-click **"Simulate Seller Quote ⚡"** action button that dynamically queries active, non-expired merchants within 3 km and submits a realistic quotation for seamless instant testing.
  - **"Accept Quote & Order 🚀" Button & Backend Trigger**:
    - Positioned an interactive emerald action button next to each vendor's price offer.
    - Handled quote acceptance triggering `POST /orders/accept-quote` with `{ quotation_id: quote.id, notes: "Accepted via Customer Portal" }`.
    - Handled error states gracefully with clean Pydantic 422 array formatting.
  - **Order Confirmation Modal & Live Stepper**:
    - Designed a celebratory confirmation screen modal (`Order Accepted & Confirmed - You're All Set! 🎉`).
    - Displays official Order ID, status badge (`ACCEPTED`), merchant contact info, estimated delivery time, and total bill.
    - Integrated a live 3-step doorstep delivery progress stepper (`✓ 1. Quote Accepted` → `🛵 2. On the Way` → `🎉 3. Delivered`) that polls order status updates triggered in real time by the vendor.
  - **Component Integration (`frontend-web/src/components/CustomerPortal.jsx`)**:
    - Replaced the inline quote view with `<CustomerRequirementQuotesView requirement={result} onReset={() => setResult(null)} />`.
  - **Backend Fallback Hardening (`backend/crud.py`)**:
    - Hardened `accept_quotation_and_create_order` to support accepting an Order ID directly as a fallback if the quote was created in the `Order` table, setting status to `ACCEPTED` and syncing requirement status.
  - **End-to-End Visual Verification**:
    - Tested live via browser subagent on `http://localhost:3000/`. Verified requirement broadcast, incoming vendor quote card rendering, clicking "Accept Quote", and modal confirmation display.

---

### Phase 18: Architectural Review & Production-Hardened Architecture Specification (`ARCHITECTURE_v2.md`)
#### Prompt 20: Comprehensive System Architecture & Production Gaps Hardening
> **User Prompt:**
> Architectural review critique addressing launch-blocking security gaps (Phone OTP/JWT, scoped row-locking quote acceptance, RBI-compliant payment split-settlement, 4-digit doorstep delivery OTP, expanded 11-state order machine, DPDP Act 2023 compliance, inventory auto-quoting, Redis task queues, and localized kirana operations).
* **Action Taken:**
  - **Auth & Zero-Trust Security**: Replaced client-supplied identity parameters (`customer_id`, `seller_id`) with Phone OTP authentication and server-side JWT derivation. Fixed quote acceptance concurrency bug with row locking (`SELECT FOR UPDATE`) and strictly scoped rejection queries (`WHERE requirement_id = :rid AND id != :qid`).
  - **Payment & Delivery Security**: Addressed RBI Payment Aggregator regulations by specifying licensed split-settlement gateways (Razorpay Route / Cashfree), Cash on Delivery (COD), 4-digit customer doorstep delivery OTP verification, and append-only ledger accounting.
  - **Latency Elimination & Auto-Quoting**: Designed hybrid auto-quoting from `inventory_items` within 500 ms to remove reverse-auction waiting latency while retaining merchant 1-tap approval/override. Added customer disambiguation review and pgvector semantic catalog mapping.
  - **Async Event-Driven Pipeline**: Decoupled ingestion into `HTTP 202 Accepted` backed by Redis task queues and background NLP workers. Replaced polling with FCM push notifications and WebSockets.
  - **Legal & DPDP Compliance**: Incorporated explicit consent, purpose limitation, pre-acceptance customer address/phone masking, FSSAI/GSTIN verification, and designated Grievance Officer framework.
  - **Documentation & Diagrams**: Created `ARCHITECTURE_v2.md` with 5 solid-line, linear-curve grayscale Mermaid diagrams (Component Architecture, Request & Auto-Quote Pipeline, Order State Machine, Sequence Flow, Entity-Relationship Schema, Observability Pipeline). Updated `ARCHITECTURE.md` and `README.md`.

---

## 2. Master Rebuild Prompt (Use This to Rebuild from Scratch)

Copy and submit the following prompt to an AI agent to completely reproduce this infrastructure, all operational scripts, tests, health metrics, and documentation from zero:

````markdown
Create a complete, production-ready full-stack "Hyperlocal Quick-Commerce" platform featuring:
1. Containerized PostgreSQL 16 database with PostGIS (for geospatial radius filtering and location queries) and pgvector (for vector search and semantic AI embeddings).
2. FastAPI backend with an AI natural language shopping demand parser, 3 km merchant matching engine, multi-category inventory management with bulk upload (JSON & CSV), order quoting, mock escrow payment settlement, and freemium billing lifecycle (2-order trial with Rs. 1,000 monthly platform fee gate).
3. Resilient error handling with automatic LLM API timeout fallbacks, malformed JSON sanitization, and graceful geospatial handling when zero merchants are in radius.
4. Comprehensive automated integration test suite (`/backend/tests`) using pytest simulating full customer-to-seller-to-payment journeys and edge cases.
5. Single-command developer orchestration (`run_dev.ps1`, `run_dev.sh`, `Makefile`) spinning up PostgreSQL PostGIS, running schema migrations, and launching FastAPI and Vite web portal concurrently.
6. React + Tailwind CSS web application (`/frontend-web`) with a Customer Portal (AI demand broadcast, incoming quotes view, mock escrow checkout modal) and a Seller Dashboard (live 3 km demand radar, itemized quote submission modal, and inventory catalog management with real-time stock toggles).
7. React Native / Expo cross-platform mobile application (`/frontend-mobile`) supporting Android, iOS, and Web.
8. Full operational lifecycle automation scripts for Windows (PowerShell) and Linux/macOS (Bash) with health monitoring, metrics, disaster recovery, and strict PSScriptAnalyzer compliance.

### Requirements:

1. **Database Architecture & Containerization**:
   - **Base Image**: `pgvector/pgvector:pg16` (PostgreSQL 16 Debian Bookworm base).
   - **Dockerfile**: Install `postgresql-16-postgis-3` and `postgresql-16-postgis-3-scripts` without recommended bloat, clean apt caches.
   - **Initialization SQL (`docker/init/01-init-extensions.sql`)**:
     - `CREATE EXTENSION IF NOT EXISTS postgis;`
     - `CREATE EXTENSION IF NOT EXISTS vector;`
     - `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";`
     - Verification notice logging installed extension versions.
   - **`docker-compose.yml`**:
     - Service `db` using image `hyperlocal-marketplace-db:16`, container name `hyperlocal-postgres`.
     - Environment variables mapped from `.env` with safe fallbacks (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `PGDATA: /var/lib/postgresql/data/pgdata`).
     - Persistent volume `postgres_data` mapped to `/var/lib/postgresql/data`.
     - Initialization scripts volume mount `./docker/init:/docker-entrypoint-initdb.d:ro`.
     - Port forwarding `5432:5432` (or host port configured in `.env` e.g. `5433:5432` if native PostgreSQL service is on 5432).
     - Native healthcheck: `pg_isready -U ${DB_USER:-postgres} -d ${DB_NAME:-hyperlocal_marketplace}` (interval 10s, timeout 5s, retries 5, start_period 15s).
     - Dedicated bridge network `hyperlocal-network`.
   - **Environment Files**: `.env.example` and `.env` configured with local development credentials and LLM API key slots (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LLM_PROVIDER=auto`).

2. **Automated Operational Scripts**:
   Create root convenience wrappers and modular scripts under `scripts/`:
   - **Encoding Standards**: Every PowerShell script MUST set UTF-8 encoding at the top to prevent OEM CP437 character corruption (`ΓÇª` instead of `…`):
     ```powershell
     [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
     $OutputEncoding = [System.Text.Encoding]::UTF8
     ```
   - **PSScriptAnalyzer Compliance**: For command success checking, avoid `-eq $null` comparisons to satisfy `PSPossibleIncorrectComparisonWithNull`. Use:
     ```powershell
     if (-not $ExitCode) { ... }
     ```
   - **Logging**: All scripts must log executed commands, stdout, stderr, and timings in verbose mode to timestamped files under `logs/`, also updating a `*_latest.log` mirror.

3. **Script Specifications**:
   - **Setup & Replication Wizard (`setup.ps1` & `scripts/setup.ps1`, `scripts/setup.sh`)**:
     - Pre-flight checks (Docker CLI, daemon response, auto-create `.env`).
     - Builds container, starts stack, waits for health.
     - Runs automated SQL verification tests:
       1. PostGIS: 3 km radius query (`ST_DWithin` using `geography(Point, 4326)`).
       2. pgvector: 3-dimensional vector cosine distance calculation (`<=>`).
       3. UUID: `uuid_generate_v4()` generation.
     - Supports `-Repair`, `-ResetData` (wipes volume), `-NoCache`, and `-Force`.
   - **Startup Script (`start.ps1` & `scripts/start.ps1`, `scripts/start.sh`)**:
     - Pre-flight verification.
     - `docker compose up -d` (with optional `-NoBuild`).
     - Port binding verification (`docker port hyperlocal-postgres`).
     - Health monitoring loop until healthy.
     - Engine ping (`pg_isready`) and Docker health probe logs.
     - PostgreSQL version and extension queries (`\dx`).
     - Server metrics monitoring (live stats, CPU/Memory, disk usage, active queries, uptime, buffer cache hit ratio).
   - **Shutdown Script (`stop.ps1` & `scripts/stop.ps1`, `scripts/stop.sh`)**:
     - Pre-shutdown check (active client queries, pre-shutdown metrics), graceful stop (`docker compose down`), volume preservation check.
   - **Health & Metrics Monitor (`health.ps1` & `scripts/health.ps1`, `scripts/health.sh`)**:
     - Standalone script to inspect container status, healthcheck logs, engine ping, resource consumption, disk usage, database size, cache hit ratio, and recent server logs at any time.

4. **FastAPI Backend Architecture, AI Engine & Routers (`/backend`)**:
   - **`requirements.txt`**: Include `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2.0`, `psycopg2-binary`, `pydantic`, `pydantic-settings`, `python-dotenv`, `geoalchemy2`, `shapely`, `pgvector`, `alembic`, and `httpx`.
   - **`database.py`**: Connection pooling, `.env` discovery, `Base`, `SessionLocal`, `get_db()` dependency.
   - **`models.py`**:
     - `users`: ID (UUID), name, phone, role (`customer`, `seller`, `admin`), location (PostGIS `POINT` in EPSG:4326 with GiST index), coordinates, address.
     - `categories`: ID (UUID), category, sub_category, unique constraint.
     - `inventory_items`: ID (UUID), seller_id (FK), product_name, price, is_available.
     - `item_categories`: M:N association table allowing a single product to map across multiple categories.
     - `requirements`: ID (UUID), customer_id (FK), raw_text, structured_json (JSONB), status.
   - **`ai_parser.py`**:
     - Multi-provider async LLM client supporting Google Gemini, OpenAI, and Anthropic Claude via REST APIs with Pydantic JSON schema output (`ParsedRequirement`, `ParsedItem`, `UrgencyLevel`).
     - Includes deterministic offline rule parser for local development and test environments when no external API keys are configured.
   - **`matching_engine.py`**:
     - Geospatial matching service executing PostGIS `ST_DWithin` 3 km radius query on indexed seller locations.
     - Computes geodesic distance with `ST_Distance`.
     - Evaluates seller inventory and category coverage against parsed shopping items, returning ranked sellers with fulfillment percentages.
   - **`schemas.py`**: Pydantic v2 schemas for Users, Categories, Inventory Items, Requirements, and `RequirementSubmitRequest` / `RequirementSubmitResponse`.
   - **`crud.py`**: PostGIS spatial queries, category linking, user geocoding, and requirement filtering.
   - **`routers/`**:
     - `health.py`: `GET /health` (deep diagnostics), `GET /` (metadata).
     - `users.py`: `POST /api/v1/users`, `GET /api/v1/users`, `GET /api/v1/users/{id}`, `PUT /api/v1/users/{id}`, `DELETE /api/v1/users/{id}`.
     - `categories.py`: `POST /api/v1/categories`, `GET /api/v1/categories`, `GET /api/v1/categories/{id}`.
     - `inventory.py`: `POST /api/v1/items`, `GET /api/v1/items/nearby` (hyperlocal radius query), `GET /api/v1/items/seller/{id}`, `PATCH /api/v1/items/{id}/availability`.
     - `requirements.py`: `POST /requirements/submit` (AI parsing + 3 km PostGIS matching pipeline), `POST /api/v1/requirements`, `GET /api/v1/requirements/nearby`, `PATCH /api/v1/requirements/{id}/status`.
   - **`main.py`**: FastAPI entrypoint with CORS, lifespan events, root route aliases, and global exception handlers.
   - **`test_api.py`**: Automated end-to-end integration test suite validating all endpoints, AI parsing, and PostGIS matching.
   - **`init_db.py` & `schema.sql`**: Table creation utility and direct SQL DDL executable via Docker `psql` or `python -m backend.init_db --seed`.

5. **Frontend Web Application (`/frontend-web`)**:
   - Modern React + Tailwind CSS application initialized via Vite.
   - **API Service Client (`src/api/client.js`)**: Communicates with FastAPI backend (`http://localhost:8000`).
   - **Navigation Header (`src/components/Header.jsx`)**: Glassmorphism navbar with live backend database health indicator (periodic ping to `/health`) and view switcher.
   - **Customer Portal (`src/components/CustomerPortal.jsx`)**:
     - Large natural language shopping prompt textarea with suggestions.
     - Location picker with presets (Wakad, Pune; Indiranagar, Bangalore) and HTML5 Geolocation API.
     - On submit: calls `POST /requirements/submit`, renders AI-extracted shopping list, urgency badge, and cards for all notified merchants within 3 km with live distance tags and in-stock items.
   - **Seller Dashboard (`src/components/SellerDashboard.jsx`)**:
     - Real-time 3 km radar feed of incoming customer demand broadcasts within the merchant's delivery zone.
     - Interactive "Accept Order & Quote Price" modal allowing merchants to input custom price quotes (₹), delivery time estimates, and fulfillment notes with instant status synchronization.

6. **Documentation**:
   - Comprehensive `README.md` covering architecture, geospatial/vector use cases, setup wizard, startup/shutdown scripts, on-demand health monitoring commands, backend dependency installation (`venv`), database initialization commands, API endpoint documentation, and concurrent backend + frontend launch commands.
   - `.gitignore` ignoring `.env`, `logs/`, `venv/`, `node_modules/`, `dist/`, `__pycache__/`, and temporary build artifacts.
````
