<#
.SYNOPSIS
    Hyperlocal Marketplace Docker Startup Script
.DESCRIPTION
    Starts the PostgreSQL 16 database with PostGIS and pgvector extensions.
    Captures all executed commands, stdout, stderr, health status, extension
    verifications, and container logs in verbose mode to a timestamped file.
.PARAMETER NoBuild
    Starts the containers without triggering a docker build.
.PARAMETER LogDir
    Directory path to store the generated log files (relative to repository root or absolute).
.PARAMETER TimeoutSeconds
    Maximum time in seconds to wait for the database container to become healthy. Default: 60.
.EXAMPLE
    .\scripts\start.ps1
.EXAMPLE
    .\scripts\start.ps1 -NoBuild
#>

[CmdletBinding()]
param (
    [switch]$NoBuild,
    [string]$LogDir = "logs",
    [int]$TimeoutSeconds = 60
)

# Set strict mode and error handling
$ErrorActionPreference = "Continue"

# Force UTF-8 encoding for external command output and stdout capture
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Resolve Workspace Root (one level up from 'scripts')
$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkspaceRoot = (Resolve-Path "$ScriptDirectory\..").Path
Set-Location -Path $WorkspaceRoot

# Prepare Logs Directory and File
$ResolvedLogDir = Join-Path $WorkspaceRoot $LogDir
if (-not (Test-Path $ResolvedLogDir)) {
    New-Item -ItemType Directory -Path $ResolvedLogDir -Force | Out-Null
}

$Timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$LogFileName = "startup_$Timestamp.log"
$LogFilePath = Join-Path $ResolvedLogDir $LogFileName
$LatestLogPath = Join-Path $ResolvedLogDir "startup_latest.log"

# -----------------------------------------------------------------------------
# Logging Utilities
# -----------------------------------------------------------------------------
function Write-Log {
    param (
        [string]$Message,
        [string]$Level = "INFO",
        [ConsoleColor]$Color = [ConsoleColor]::White
    )
    $TimeStr = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss.fff")
    $LogLine = "[$TimeStr] [$Level] $Message"
    
    # Write to File
    Add-Content -Path $LogFilePath -Value $LogLine -Encoding utf8
    
    # Write to Console with colors
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

# -----------------------------------------------------------------------------
# Command Execution in Verbose Mode
# -----------------------------------------------------------------------------
function Invoke-VerboseCommand {
    param (
        [string]$CommandLine,
        [bool]$FailOnError = $true
    )
    Write-Log "EXECUTING: $CommandLine" "CMD" Yellow
    
    # Record starting timestamp
    $StartTime = Get-Date
    
    # Run command and capture output (both stdout and stderr)
    $Output = @()
    try {
        $Output = Invoke-Expression "$CommandLine 2>&1"
    } catch {
        Write-Log "Execution error: $_" "ERROR" Red
        if ($FailOnError) { throw $_ }
    }
    
    $ExitCode = $LASTEXITCODE
    $Duration = ((Get-Date) - $StartTime).TotalSeconds
    
    # Write raw output to log file and console
    foreach ($line in $Output) {
        $lineStr = [string]$line
        Add-Content -Path $LogFilePath -Value "    | $lineStr" -Encoding utf8
        Write-Host "    $lineStr" -ForegroundColor DarkGray
    }
    
    if (-not $ExitCode) {
        Write-Log "Command completed successfully in $($Duration.ToString('0.00'))s (exit code 0)" "SUCCESS" Green
    } else {
        Write-Log "Command failed in $($Duration.ToString('0.00'))s with exit code $ExitCode" "WARN" Yellow
        if ($FailOnError) {
            throw "Command failed: $CommandLine (Exit code: $ExitCode)"
        }
    }
    
    return [PSCustomObject]@{
        ExitCode = $ExitCode
        Output = $Output
    }
}

# -----------------------------------------------------------------------------
# Script Main Flow
# -----------------------------------------------------------------------------
try {
    Write-Section "HYPERLOCAL MARKETPLACE - DOCKER STARTUP SEQUENCE"
    Write-Log "Workspace root: $WorkspaceRoot" "INFO" DarkCyan
    Write-Log "Startup log destination: $LogFilePath" "INFO" DarkCyan

    # Step 1: Pre-flight Verification
    Write-Section "STEP 1: PRE-FLIGHT SYSTEM VERIFICATION"
    
    # Check Docker CLI
    $dockerCheck = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCheck) {
        throw "Docker CLI was not found in PATH. Please install Docker or ensure it is in system PATH."
    }
    
    # Check Docker Daemon
    Write-Log "Verifying Docker engine daemon connectivity..." "INFO" White
    $dockerInfo = Invoke-VerboseCommand "docker info" -FailOnError $false
    if ($dockerInfo.ExitCode -ne 0) {
        throw "Docker daemon is not responding. Please start Docker Desktop or Rancher Desktop and retry."
    }

    # Check .env configuration
    $envPath = Join-Path $WorkspaceRoot ".env"
    $envExamplePath = Join-Path $WorkspaceRoot ".env.example"
    if (-not (Test-Path $envPath)) {
        if (Test-Path $envExamplePath) {
            Write-Log ".env file not found. Auto-generating from .env.example..." "WARN" Yellow
            Copy-Item $envExamplePath $envPath
            Write-Log ".env file created successfully." "SUCCESS" Green
        } else {
            Write-Log "Warning: Neither .env nor .env.example was found. Relying on default environment variables." "WARN" Yellow
        }
    } else {
        Write-Log "Environment configuration verified (.env exists)." "INFO" Green
    }

    # Step 2: Build & Start Containers
    Write-Section "STEP 2: STARTING DOCKER CONTAINERS"
    $composeUpCmd = if ($NoBuild) {
        "docker compose up -d"
    } else {
        "docker compose up -d --build"
    }
    
    $null = Invoke-VerboseCommand $composeUpCmd -FailOnError $true

    # Step 2.1: Verify Port Bindings
    Write-Log "Verifying container port bindings..." "INFO" White
    $null = Invoke-VerboseCommand "docker port hyperlocal-postgres" -FailOnError $false

    # Step 3: Wait for Healthcheck & Engine Readiness
    Write-Section "STEP 3: MONITORING DATABASE HEALTH & READINESS"
    Write-Log "Waiting for PostgreSQL container (hyperlocal-postgres) to reach 'healthy' state (max timeout: ${TimeoutSeconds}s)..." "INFO" Yellow
    
    $Elapsed = 0
    $CheckInterval = 3
    $IsHealthy = $false

    while ($Elapsed -lt $TimeoutSeconds) {
        Start-Sleep -Seconds $CheckInterval
        $Elapsed += $CheckInterval
        
        $psResult = docker compose ps --format json | ConvertFrom-Json -ErrorAction SilentlyContinue
        $dbStatus = ""
        $dbHealth = ""
        
        if ($psResult) {
            # Normalize to array if single object returned
            $services = @($psResult)
            $dbService = $services | Where-Object { $_.Service -eq "db" -or $_.Name -like "*postgres*" } | Select-Object -First 1
            if ($dbService) {
                $dbStatus = $dbService.Status
                $dbHealth = $dbService.Health
            }
        }
        
        Write-Log "Check after ${Elapsed}s: Status = '$dbStatus', Health = '$dbHealth'" "INFO" DarkGray
        
        if ($dbHealth -eq "healthy" -or $dbStatus -like "*healthy*") {
            $IsHealthy = $true
            break
        }
    }

    if (-not $IsHealthy) {
        Write-Log "Container did not reach 'healthy' state within $TimeoutSeconds seconds." "WARN" Red
    } else {
        Write-Log "Database container is HEALTHY and ready to accept connections!" "SUCCESS" Green
    }

    # Step 3.1: Healthcheck Execution Logs and Native pg_isready probe
    Write-Log "Fetching internal Docker healthcheck log history..." "INFO" White
    $null = Invoke-VerboseCommand 'docker inspect --format "{{range .State.Health.Log}}[{{.End}}] ExitCode={{.ExitCode}} Output={{.Output}}{{end}}" hyperlocal-postgres' -FailOnError $false

    Write-Log "Running native pg_isready connection test directly against database engine..." "INFO" White
    $null = Invoke-VerboseCommand 'docker compose exec -T db pg_isready -U postgres -d hyperlocal_marketplace' -FailOnError $false

    # Step 4: Verification of PostgreSQL Extensions & Engine Details
    Write-Section "STEP 4: VERIFYING POSTGRESQL ENGINE & EXTENSIONS"
    Write-Log "Querying PostgreSQL server version and build info..." "INFO" White
    $null = Invoke-VerboseCommand 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "SELECT version();"' -FailOnError $false

    Write-Log "Running SQL verification query for PostGIS and pgvector extensions..." "INFO" White
    $verifyCmd = 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "\dx"'
    $null = Invoke-VerboseCommand $verifyCmd -FailOnError $false

    # Step 5: Server Metrics & Resource Consumption
    Write-Section "STEP 5: SERVER METRICS & RESOURCE MONITORING"
    Write-Log "Capturing real-time container CPU, Memory, Network I/O, Block I/O & Process Count..." "INFO" Cyan
    $null = Invoke-VerboseCommand 'docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}"' -FailOnError $false

    Write-Log "Checking container lifecycle state, uptime, restart count & OOM status..." "INFO" White
    $null = Invoke-VerboseCommand 'docker inspect --format "Status: {{.State.Status}} | StartedAt: {{.State.StartedAt}} | Restarts: {{.RestartCount}} | OOMKilled: {{.State.OOMKilled}} | Platform: {{.Platform}}" hyperlocal-postgres' -FailOnError $false

    Write-Log "Inspecting running OS processes inside container (docker top)..." "INFO" White
    $null = Invoke-VerboseCommand 'docker top hyperlocal-postgres' -FailOnError $false

    Write-Log "Checking persistent volume storage and disk space..." "INFO" White
    $null = Invoke-VerboseCommand 'docker compose exec -T db df -h /var/lib/postgresql/data' -FailOnError $false

    Write-Log "Querying database operational metrics (Size, Connections, Cache Hit Ratio)..." "INFO" White
    $metricsSql = "SELECT pg_size_pretty(pg_database_size('hyperlocal_marketplace')) AS db_size, (SELECT count(*) FROM pg_stat_activity) AS total_connections, (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') AS active_queries, now() - pg_postmaster_start_time() AS engine_uptime, COALESCE(round(sum(heap_blks_hit) * 100.0 / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2), 100.0) AS cache_hit_pct FROM pg_statio_user_tables;"
    $null = Invoke-VerboseCommand "docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c `"$metricsSql`"" -FailOnError $false

    # Step 6: Capture Container Startup Logs
    Write-Section "STEP 6: CAPTURING RECENT CONTAINER INTERNAL LOGS"
    Write-Log "Fetching internal PostgreSQL server logs (last 30 lines)..." "INFO" White
    $logsCmd = "docker compose logs --tail=30 --no-color db"
    $null = Invoke-VerboseCommand $logsCmd -FailOnError $false

    # Mirror to startup_latest.log for easy access
    Copy-Item -Path $LogFilePath -Destination $LatestLogPath -Force
    
    # Step 7: Summary
    Write-Section "STARTUP COMPLETED SUCCESSFULLY"
    Write-Log "Docker environment is UP and RUNNING." "SUCCESS" Green
    Write-Log "Database Port   : localhost:5432" "INFO" Cyan
    Write-Log "Database Name   : hyperlocal_marketplace" "INFO" Cyan
    Write-Log "Primary User    : postgres" "INFO" Cyan
    Write-Log "Verbose Log     : $LogFilePath" "INFO" Cyan
    Write-Log "Latest Log Link : $LatestLogPath" "INFO" Cyan
    Write-Log "Next Step       : Run .\scripts\stop.ps1 when you wish to shutdown the environment." "INFO" White
    
    exit 0
} catch {
    Write-Section "STARTUP FAILED"
    Write-Log "Fatal error encountered during startup: $_" "ERROR" Red
    Write-Log "Check full trace above or in log file: $LogFilePath" "ERROR" Red
    
    # Attempt to copy log even on error
    if (Test-Path $LogFilePath) {
        Copy-Item -Path $LogFilePath -Destination $LatestLogPath -Force -ErrorAction SilentlyContinue
    }
    exit 1
}
