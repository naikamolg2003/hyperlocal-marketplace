#!/usr/bin/env bash
# =============================================================================
# Hyperlocal Marketplace Docker Startup Script (Bash / POSIX / WSL / macOS)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$WORKSPACE_ROOT"

LOG_DIR="${1:-logs}"
TIMEOUT_SECONDS="${2:-60}"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
LOG_FILE="$LOG_DIR/startup_${TIMESTAMP}.log"
LATEST_LOG="$LOG_DIR/startup_latest.log"

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
log "INFO" "HYPERLOCAL MARKETPLACE - DOCKER STARTUP SEQUENCE"
log "INFO" "======================================================================"
log "INFO" "Workspace Root : $WORKSPACE_ROOT"
log "INFO" "Startup Log    : $LOG_FILE"

# Step 1: Pre-flight checks
log "INFO" "--- Step 1: Pre-flight Checks ---"
if ! command -v docker &>/dev/null; then
    log "ERROR" "Docker command not found in PATH."
    exit 1
fi

log_cmd "docker info"

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    log "WARN" "Creating .env from .env.example..."
    cp .env.example .env
fi

# Step 2: Start containers
log "INFO" "--- Step 2: Starting Docker Containers ---"
log_cmd "docker compose up -d --build"

# Step 2.1: Verify Port Bindings
log "INFO" "--- Step 2.1: Port Bindings ---"
log_cmd "docker port hyperlocal-postgres"

# Step 3: Wait for healthy state
log "INFO" "--- Step 3: Waiting for Database Healthcheck (${TIMEOUT_SECONDS}s max) ---"
elapsed=0
interval=3
is_healthy=0

while [ $elapsed -lt "$TIMEOUT_SECONDS" ]; do
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
    log "SUCCESS" "Database container is HEALTHY and ready!"
else
    log "WARN" "Container did not report healthy within timeout."
fi

# Step 3.1: Healthcheck History & Engine Ping
log "INFO" "--- Step 3.1: Healthcheck Log & Engine Ping ---"
log_cmd 'docker inspect --format "{{range .State.Health.Log}}[{{.End}}] ExitCode={{.ExitCode}} Output={{.Output}}{{end}}" hyperlocal-postgres'
log_cmd "docker compose exec -T db pg_isready -U postgres -d hyperlocal_marketplace"

# Step 4: Verification of extensions & version
log "INFO" "--- Step 4: Verifying PostgreSQL Version & Extensions ---"
log_cmd 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "SELECT version();"'
log_cmd 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "\dx"'

# Step 5: Server Metrics & Resource Consumption
log "INFO" "--- Step 5: Server Metrics & Resource Monitoring ---"
log_cmd 'docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}"'
log_cmd 'docker inspect --format "StartedAt: {{.State.StartedAt}} | Restarts: {{.RestartCount}} | OOMKilled: {{.State.OOMKilled}}" hyperlocal-postgres'
log_cmd "docker top hyperlocal-postgres"
log_cmd "docker compose exec -T db df -h /var/lib/postgresql/data"
log_cmd 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "SELECT pg_size_pretty(pg_database_size('\''hyperlocal_marketplace'\'')) AS db_size, (SELECT count(*) FROM pg_stat_activity) AS total_connections, (SELECT count(*) FROM pg_stat_activity WHERE state = '\''active'\'') AS active_queries, now() - pg_postmaster_start_time() AS uptime;"'

# Step 6: Capture container logs
log "INFO" "--- Step 6: Capturing Internal Server Logs ---"
log_cmd "docker compose logs --tail=30 --no-color db"

cp "$LOG_FILE" "$LATEST_LOG"

log "INFO" "======================================================================"
log "SUCCESS" "Hyperlocal Marketplace Docker environment is UP and RUNNING."
log "INFO" "Log saved to: $LOG_FILE (Mirrored to $LATEST_LOG)"
log "INFO" "======================================================================"
