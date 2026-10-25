#!/usr/bin/env bash
# =============================================================================
# Hyperlocal Marketplace Docker Shutdown Script (Bash / POSIX / WSL / macOS)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$WORKSPACE_ROOT"

LOG_DIR="${1:-logs}"
TIMEOUT="${2:-15}"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
LOG_FILE="$LOG_DIR/shutdown_${TIMESTAMP}.log"
LATEST_LOG="$LOG_DIR/shutdown_latest.log"

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
log "INFO" "HYPERLOCAL MARKETPLACE - DOCKER SHUTDOWN SEQUENCE"
log "INFO" "======================================================================"
log "INFO" "Workspace Root : $WORKSPACE_ROOT"
log "INFO" "Shutdown Log   : $LOG_FILE"

# Step 1: Pre-shutdown check
log "INFO" "--- Step 1: Pre-shutdown System Checks ---"
log_cmd "docker info"

# Step 2: Shutdown containers
log "INFO" "--- Step 2: Gracefully Stopping Docker Containers ---"
log_cmd "docker compose down -t $TIMEOUT"

# Step 3: Verify post-shutdown status
log "INFO" "--- Step 3: Verifying Containers Stopped ---"
log_cmd "docker compose ps"

cp "$LOG_FILE" "$LATEST_LOG"

log "INFO" "======================================================================"
log "SUCCESS" "Docker environment has been shut down cleanly."
log "INFO" "Log saved to: $LOG_FILE (Mirrored to $LATEST_LOG)"
log "INFO" "======================================================================"
