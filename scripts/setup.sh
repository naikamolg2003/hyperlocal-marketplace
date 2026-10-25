#!/usr/bin/env bash
# =============================================================================
# Hyperlocal Marketplace Setup & Replication Script (Bash / Linux / macOS / WSL)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$WORKSPACE_ROOT"

LOG_DIR="${1:-logs}"
TIMEOUT="${2:-60}"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
LOG_FILE="$LOG_DIR/setup_${TIMESTAMP}.log"
LATEST_LOG="$LOG_DIR/setup_latest.log"

log() {
    local level="$1"; shift
    local msg="$*"
    local time_str="$(date +"%Y-%m-%d %H:%M:%S")"
    echo "[$time_str] [$level] $msg" | tee -a "$LOG_FILE"
}

log_cmd() {
    local cmd="$*"
    log "CMD" "EXECUTING: $cmd"
    set +e
    eval "$cmd" 2>&1 | while IFS= read -r line; do
        echo "    | $line" >> "$LOG_FILE"
        echo "    $line"
    done
    local status="${PIPESTATUS[0]}"
    set -e
    if [ "$status" -eq 0 ]; then
        log "SUCCESS" "Command completed successfully (exit code 0)"
    else
        log "WARN" "Command exited with status $status"
        return "$status"
    fi
}

log "INFO" "======================================================================"
log "INFO" "HYPERLOCAL MARKETPLACE - SETUP & DISASTER RECOVERY WIZARD"
log "INFO" "======================================================================"
log "INFO" "Workspace Root : $WORKSPACE_ROOT"
log "INFO" "Setup Log File : $LOG_FILE"

# Step 1: System prerequisites
log "INFO" "--- Step 1: Checking System & Tooling Prerequisites ---"
if ! command -v docker &>/dev/null; then
    log "ERROR" "Docker is not installed or not in PATH."
    exit 1
fi

log_cmd "docker info"
log_cmd "docker compose version"

# Step 2: Validate Files & Config
log "INFO" "--- Step 2: Validating Files & Configuration ---"
for file in Dockerfile docker-compose.yml docker/init/01-init-extensions.sql; do
    if [ ! -f "$file" ]; then
        log "ERROR" "Missing required file: $file"
        exit 1
    fi
    log "INFO" "Verified file: $file"
done

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    log "WARN" "Creating .env from .env.example..."
    cp .env.example .env
fi

# Step 3: Build image
log "INFO" "--- Step 3: Building Custom PostgreSQL Image ---"
log_cmd "docker compose build"

# Step 4: Launch container
log "INFO" "--- Step 4: Launching Containers ---"
log_cmd "docker compose up -d"

# Step 5: Wait for healthcheck
log "INFO" "--- Step 5: Awaiting Database Healthcheck (${TIMEOUT}s max) ---"
elapsed=0
interval=3
is_healthy=0

while [ $elapsed -lt "$TIMEOUT" ]; do
    sleep "$interval"
    elapsed=$((elapsed + interval))
    status="$(docker compose ps --format json 2>/dev/null || true)"
    if echo "$status" | grep -qi '"healthy"'; then
        is_healthy=1
        break
    fi
    log "INFO" "Healthcheck pending after ${elapsed}s..."
done

if [ "$is_healthy" -eq 1 ]; then
    log "SUCCESS" "Database container is HEALTHY and accepting connections!"
else
    log "ERROR" "Database container failed to reach healthy status."
    exit 1
fi

# Step 6: Test suite
log "INFO" "--- Step 6: Running Automated Verification Tests ---"
log "INFO" "Test 1/4: Extensions query"
log_cmd 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "\dx"'

log "INFO" "Test 2/4: PostGIS 3km calculation"
log_cmd 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "SELECT PostGIS_Version(); SELECT ST_DWithin(ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326)::geography, ST_SetSRID(ST_MakePoint(77.6000, 12.9750), 4326)::geography, 3000) AS hyperlocal_3km_match;"'

log "INFO" "Test 3/4: pgvector distance query"
log_cmd 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "SELECT '\''[1,2,3]'\''::vector <=> '\''[1,2,3]'\''::vector AS cosine_dist;"'

log "INFO" "Test 4/4: UUID generation"
log_cmd 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "SELECT uuid_generate_v4();"'

# Step 7: Initialize Core Backend Schema & Tables
log "INFO" "--- Step 7: Initializing Core Backend Schema & Tables ---"
if [ -f "backend/schema.sql" ]; then
    log_cmd "cat backend/schema.sql | docker compose exec -T db psql -U postgres -d hyperlocal_marketplace"
fi

# Step 8: Container logs
log "INFO" "--- Step 8: Capturing Container Logs ---"
log_cmd "docker compose logs --tail=30 --no-color db"

cp "$LOG_FILE" "$LATEST_LOG"

log "INFO" "======================================================================"
log "SUCCESS" "Setup & Replication completed successfully!"
log "INFO" "Logs saved to: $LOG_FILE (Mirrored to $LATEST_LOG)"
log "INFO" "======================================================================"
