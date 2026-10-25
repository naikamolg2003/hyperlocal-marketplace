<#
.SYNOPSIS
    Hyperlocal Marketplace - Health & Metrics Monitoring Script
.DESCRIPTION
    Inspects running Docker containers, queries health status, captures server
    metrics (CPU, Memory, Disk, Network I/O), verifies database engine readiness,
    and logs operational statistics.
.EXAMPLE
    .\scripts\health.ps1
.EXAMPLE
    .\health.ps1
#>

[CmdletBinding()]
param (
    [string]$LogDir = "logs"
)

$ErrorActionPreference = "Continue"

# Force UTF-8 encoding for external command output and stdout capture
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkspaceRoot = (Resolve-Path "$ScriptDirectory\..").Path
Set-Location -Path $WorkspaceRoot

$ResolvedLogDir = Join-Path $WorkspaceRoot $LogDir
if (-not (Test-Path $ResolvedLogDir)) {
    New-Item -ItemType Directory -Path $ResolvedLogDir -Force | Out-Null
}

$Timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$LogFilePath = Join-Path $ResolvedLogDir "health_$Timestamp.log"
$LatestLogPath = Join-Path $ResolvedLogDir "health_latest.log"

function Write-Log {
    param (
        [string]$Message,
        [string]$Level = "INFO",
        [ConsoleColor]$Color = [ConsoleColor]::White
    )
    $TimeStr = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss.fff")
    $LogLine = "[$TimeStr] [$Level] $Message"
    Add-Content -Path $LogFilePath -Value $LogLine -Encoding utf8
    $ConsolePrefix = "[$TimeStr] [$Level]"
    Write-Host "$ConsolePrefix " -NoNewline -ForegroundColor DarkGray
    Write-Host $Message -ForegroundColor $Color
}

function Write-Section {
    param ([string]$Title)
    $Separator = "=" * 70
    Write-Log $Separator "INFO" Gray
    Write-Log $Title "INFO" Cyan
    Write-Log $Separator "INFO" Gray
}

function Invoke-VerboseCommand {
    param (
        [string]$CommandLine,
        [bool]$FailOnError = $false
    )
    Write-Log "EXECUTING: $CommandLine" "CMD" Yellow
    $StartTime = Get-Date
    $Output = @()
    try {
        $Output = Invoke-Expression "$CommandLine 2>&1"
    }
    catch {
        Write-Log "Execution error: $_" "ERROR" Red
        if ($FailOnError) { throw $_ }
    }
    $ExitCode = $LASTEXITCODE
    $Duration = ((Get-Date) - $StartTime).TotalSeconds
    foreach ($line in $Output) {
        $lineStr = [string]$line
        Add-Content -Path $LogFilePath -Value "    | $lineStr" -Encoding utf8
        Write-Host "    $lineStr" -ForegroundColor DarkGray
    }
    if (-not $ExitCode) {
        Write-Log "Completed in $($Duration.ToString('0.00'))s (exit code 0)" "SUCCESS" Green
    }
    else {
        Write-Log "Command exited with code $ExitCode in $($Duration.ToString('0.00'))s" "WARN" Yellow
    }
    return [PSCustomObject]@{
        ExitCode = $ExitCode
        Output   = $Output
    }
}

try {
    Write-Section "HYPERLOCAL MARKETPLACE - HEALTH & SERVER METRICS REPORT"
    Write-Log "Report generated at : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" "INFO" White
    Write-Log "Log file location   : $LogFilePath" "INFO" DarkCyan

    # Check 1: Container State & Port Forwarding
    Write-Section "1. CONTAINER STATUS & PORT BINDINGS"
    Invoke-VerboseCommand "docker compose ps" | Out-Null
    Invoke-VerboseCommand "docker port hyperlocal-postgres" | Out-Null

    # Check 2: Healthcheck & Engine Readiness Probe
    Write-Section "2. HEALTH STATUS & READINESS PROBES"
    Write-Log "Docker Container Health State:" "INFO" White
    Invoke-VerboseCommand 'docker inspect --format "Status: {{.State.Status}} | Health: {{.State.Health.Status}} | FailingStreak: {{.State.Health.FailingStreak}}" hyperlocal-postgres' | Out-Null

    Write-Log "Recent Healthcheck Probes Log:" "INFO" White
    Invoke-VerboseCommand 'docker inspect --format "{{range .State.Health.Log}}[{{.End}}] ExitCode={{.ExitCode}} Output={{.Output}}{{end}}" hyperlocal-postgres' | Out-Null

    Write-Log "Direct PostgreSQL Engine Ping (pg_isready):" "INFO" White
    Invoke-VerboseCommand "docker compose exec -T db pg_isready -U postgres -d hyperlocal_marketplace" | Out-Null

    # Check 3: Container Server Metrics (CPU, Memory, I/O, PIDs)
    Write-Section "3. CONTAINER RESOURCE METRICS (CPU / MEMORY / I/O)"
    Invoke-VerboseCommand 'docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}"' | Out-Null

    Write-Log "Container Lifecycle & Reliability:" "INFO" White
    Invoke-VerboseCommand 'docker inspect --format "StartedAt: {{.State.StartedAt}} | Restarts: {{.RestartCount}} | OOMKilled: {{.State.OOMKilled}} | Platform: {{.Platform}}" hyperlocal-postgres' | Out-Null

    # Check 4: Host & Persistent Storage Metrics
    Write-Section "4. STORAGE & VOLUME DISK UTILIZATION"
    Write-Log "Container filesystem space for PGDATA:" "INFO" White
    Invoke-VerboseCommand "docker compose exec -T db df -h /var/lib/postgresql/data" | Out-Null

    # Check 5: Database Engine & Workload Metrics
    Write-Section "5. DATABASE ENGINE & WORKLOAD METRICS"
    Write-Log "Querying Database Size, Active Connections, Uptime & Cache Hit Ratio:" "INFO" White
    $metricsSql = "SELECT pg_size_pretty(pg_database_size('hyperlocal_marketplace')) AS db_size, (SELECT count(*) FROM pg_stat_activity) AS total_connections, (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') AS active_queries, now() - pg_postmaster_start_time() AS engine_uptime, COALESCE(round(sum(heap_blks_hit) * 100.0 / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2), 100.0) AS cache_hit_pct FROM pg_statio_user_tables;"
    Invoke-VerboseCommand "docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c `"$metricsSql`"" | Out-Null

    Write-Log "PostgreSQL Installed Extensions:" "INFO" White
    Invoke-VerboseCommand 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "\dx"' | Out-Null

    # Check 6: Recent Logs & Error Inspection
    Write-Section "6. RECENT SERVER LOGS & ANOMALY SCAN"
    Invoke-VerboseCommand "docker compose logs --tail=20 --no-color db" | Out-Null

    Copy-Item -Path $LogFilePath -Destination $LatestLogPath -Force

    Write-Section "HEALTH & METRICS CHECK COMPLETED"
    Write-Log "All operational health and metric checks completed successfully." "SUCCESS" Green
    Write-Log "Report saved to: $LatestLogPath" "INFO" Cyan
    exit 0
}
catch {
    Write-Section "HEALTH CHECK FAILED"
    Write-Log "Error running health checks: $_" "ERROR" Red
    exit 1
}
