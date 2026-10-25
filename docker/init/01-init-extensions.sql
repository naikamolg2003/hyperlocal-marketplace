-- =============================================================================
-- Hyperlocal Marketplace Database Initialization
-- Automatically executed on first container startup by PostgreSQL entrypoint
-- =============================================================================

-- 1. Enable PostGIS for geospatial indexing and radius filtering (e.g. 3km radius)
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Enable pgvector for semantic search, vector embeddings, and similarity matching
CREATE EXTENSION IF NOT EXISTS vector;

-- 3. Enable uuid-ossp for distributed primary key generation (UUIDs)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log installed extension versions to container logs for verification
DO $$
BEGIN
    RAISE NOTICE '=======================================================';
    RAISE NOTICE 'Hyperlocal Database Extensions Initialized Successfully:';
    RAISE NOTICE '  - PostGIS version: %', (SELECT extversion FROM pg_extension WHERE extname = 'postgis');
    RAISE NOTICE '  - pgvector version: %', (SELECT extversion FROM pg_extension WHERE extname = 'vector');
    RAISE NOTICE '  - uuid-ossp version: %', (SELECT extversion FROM pg_extension WHERE extname = 'uuid-ossp');
    RAISE NOTICE '=======================================================';
END $$;
