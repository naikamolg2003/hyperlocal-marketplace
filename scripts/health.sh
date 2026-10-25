#!/usr/bin/env bash
# =============================================================================
# Hyperlocal Marketplace - Health & Metrics Monitoring Script (Bash)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$WORKSPACE_ROOT"

LOG_DIR="${1:-logs}"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
LOG_FILE="$LOG_DIR/health_${TIMESTAMP}.log"
LATEST_LOG="$LOG_DIR/health_latest.log"

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
        log "SUCCESS" "Completed successfully (exit code 0)"
    else
        log "WARN" "Exited with code $status"
    fi
}

log "INFO" "======================================================================"
log "INFO" "HYPERLOCAL MARKETPLACE - HEALTH & SERVER METRICS REPORT"
log "INFO" "======================================================================"
log "INFO" "Log destination: $LOG_FILE"

# 1. Container Status & Port Bindings
log "INFO" "--- 1. Container Status & Port Forwarding ---"
log_cmd "docker compose ps"
log_cmd "docker port hyperlocal-postgres"

# 2. Health & Readiness Probe
log "INFO" "--- 2. Health Status & Readiness Probe ---"
log_cmd 'docker inspect --format "Status: {{.State.Status}} | Health: {{.State.Health.Status}} | FailingStreak: {{.State.Health.FailingStreak}}" hyperlocal-postgres'
log_cmd 'docker inspect --format "{{range .State.Health.Log}}[{{.End}}] ExitCode={{.ExitCode}} Output={{.Output}}{{end}}" hyperlocal-postgres'
log_cmd "docker compose exec -T db pg_isready -U postgres -d hyperlocal_marketplace"

# 3. Server Resource Metrics
log "INFO" "--- 3. Server Resource Metrics (CPU, Memory, I/O) ---"
log_cmd 'docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}"'
log_cmd 'docker inspect --format "StartedAt: {{.State.StartedAt}} | Restarts: {{.RestartCount}} | OOMKilled: {{.State.OOMKilled}}" hyperlocal-postgres'
log_cmd "docker top hyperlocal-postgres"

# 4. Storage & Volume Metrics
log "INFO" "--- 4. Storage & Disk Utilization ---"
log_cmd "docker compose exec -T db df -h /var/lib/postgresql/data"

# 5. Database Workload & Health Metrics
log "INFO" "--- 5. Database Engine & Workload Metrics ---"
log_cmd 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "SELECT pg_size_pretty(pg_database_size('\''hyperlocal_marketplace'\'')) AS db_size, (SELECT count(*) FROM pg_stat_activity) AS total_connections, (SELECT count(*) FROM pg_stat_activity WHERE state = '\''active'\'') AS active_queries, now() - pg_postmaster_start_time() AS engine_uptime;"'
log_cmd 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "\dx"'

# 6. Recent Logs
log "INFO" "--- 6. Recent Server Logs ---"
log_cmd "docker compose logs --tail=20 --no-color db"

cp "$LOG_FILE" "$LATEST_LOG"

log "INFO" "======================================================================"
log "SUCCESS" "Health and server metrics report generated successfully."
log "INFO" "Report saved to: $LOG_FILE (Mirrored to $LATEST_LOG)"
log "INFO" "======================================================================"
