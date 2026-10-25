<#
.SYNOPSIS
    Hyperlocal Marketplace Docker Setup & Disaster Recovery Script
.DESCRIPTION
    Automates complete setup, replication to a new machine, or disaster recovery
    of the PostgreSQL 16 + PostGIS + pgvector Docker environment.
    
    Capabilities:
    1. Replicate the setup from scratch on any new machine.
    2. Recover / Repair a broken or corrupted Docker installation.
    3. Validate all system prerequisites (Docker, Compose, daemon, ports).
    4. Build the custom database image with all dependencies.
    5. Execute automated test suite for PostGIS (3km radius), pgvector, and UUIDs.
    6. Record all executed commands and outputs to a verbose log file.
.PARAMETER Repair
    Performs a clean repair by removing existing containers, networks, and rebuilding the image.
.PARAMETER ResetData
    Removes the persistent 'postgres_data' volume to fix database corruption. Prompts for confirmation unless -Force is specified.
.PARAMETER NoCache
    Forces a fresh Docker build without using any cached image layers.
.PARAMETER Force
    Bypasses interactive confirmation prompts.
.PARAMETER LogDir
    Directory path where setup logs are stored (default: 'logs').
.PARAMETER TimeoutSeconds
    Maximum time in seconds to wait for the container to become healthy (default: 60).
.EXAMPLE
    # First-time setup on a new machine
    .\setup.ps1
.EXAMPLE
    # Rebuild from scratch if setup is broken or corrupted
    .\setup.ps1 -Repair -NoCache
.EXAMPLE
    # Complete factory reset including database volume
    .\setup.ps1 -Repair -ResetData -Force
#>

[CmdletBinding()]
param (
    [switch]$Repair,
    [switch]$ResetData,
    [switch]$NoCache,
    [switch]$Force,
    [string]$LogDir = "logs",
    [int]$TimeoutSeconds = 60
)

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
$LogFileName = "setup_$Timestamp.log"
$LogFilePath = Join-Path $ResolvedLogDir $LogFileName
$LatestLogPath = Join-Path $ResolvedLogDir "setup_latest.log"

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

# -----------------------------------------------------------------------------
# Command Execution in Verbose Mode
# -----------------------------------------------------------------------------
function Invoke-VerboseCommand {
    param (
        [string]$CommandLine,
        [bool]$FailOnError = $true
    )
    Write-Log "EXECUTING: $CommandLine" "CMD" Yellow
    
    $StartTime = Get-Date
    $Output = @()
    try {
        $Output = Invoke-Expression "$CommandLine 2>&1"
    } catch {
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
        Write-Log "Command completed successfully in $($Duration.ToString('0.00'))s (exit code 0)" "SUCCESS" Green
    } else {
        Write-Log "Command exited with code $ExitCode" "WARN" Yellow
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
    Write-Section "HYPERLOCAL MARKETPLACE - SETUP & DISASTER RECOVERY WIZARD"
    Write-Log "Workspace root: $WorkspaceRoot" "INFO" DarkCyan
    Write-Log "Setup log destination: $LogFilePath" "INFO" DarkCyan

    # Safety confirmation for -ResetData
    if ($ResetData -and (-not $Force)) {
        Write-Warning "CAUTION: -ResetData flag is set! This will permanently delete your stored PostgreSQL data volume."
        $confirm = Read-Host "Are you sure you want to delete and reset the database volume? (type 'yes' to proceed)"
        if ($confirm -ne "yes") {
            Write-Log "Operation cancelled by user." "WARN" Yellow
            exit 0
        }
    }

    # Step 1: System & Tooling Prerequisites
    Write-Section "STEP 1: VERIFYING SYSTEM & TOOLING PREREQUISITES"
    
    # 1.1 Check Docker CLI
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCmd) {
        Write-Log "ERROR: Docker CLI is not installed or not found in PATH." "ERROR" Red
        Write-Log "Please install Docker Desktop (https://www.docker.com/products/docker-desktop/) or Rancher Desktop." "INFO" Yellow
        throw "Docker CLI missing."
    }
    Write-Log "Docker CLI detected: $($dockerCmd.Source)" "SUCCESS" Green

    # 1.2 Check Docker Daemon
    Write-Log "Checking Docker daemon connectivity..." "INFO" White
    $daemonCheck = Invoke-VerboseCommand "docker info" -FailOnError $false
    if ($daemonCheck.ExitCode -ne 0) {
        Write-Log "Docker daemon is not running. Please start Docker Desktop or the Docker service and retry." "ERROR" Red
        throw "Docker daemon not running."
    }
    Write-Log "Docker engine daemon is ACTIVE." "SUCCESS" Green

    # 1.3 Check Docker Compose plugin
    Write-Log "Verifying Docker Compose capability..." "INFO" White
    $composeCheck = Invoke-VerboseCommand "docker compose version" -FailOnError $false
    if ($composeCheck.ExitCode -ne 0) {
        Write-Log "Docker Compose v2 plugin is required." "ERROR" Red
        throw "Docker Compose missing."
    }

    # Step 2: Workspace Scaffolding & Configuration
    Write-Section "STEP 2: VALIDATING WORKSPACE FILES & ENVIRONMENT"

    # Required files list
    $requiredFiles = @(
        "Dockerfile",
        "docker-compose.yml",
        "docker\init\01-init-extensions.sql"
    )

    foreach ($file in $requiredFiles) {
        $filePath = Join-Path $WorkspaceRoot $file
        if (-not (Test-Path $filePath)) {
            throw "Critical project file is missing: $file at $filePath"
        }
        Write-Log "Verified: $file exists." "INFO" DarkGray
    }

    # Check .env configuration
    $envPath = Join-Path $WorkspaceRoot ".env"
    $envExamplePath = Join-Path $WorkspaceRoot ".env.example"

    if (-not (Test-Path $envPath)) {
        if (Test-Path $envExamplePath) {
            Write-Log ".env not found. Creating from .env.example template..." "WARN" Yellow
            Copy-Item $envExamplePath $envPath
            Write-Log ".env generated successfully." "SUCCESS" Green
        } else {
            Write-Log "Warning: No .env or .env.example found. Default Docker Compose variables will be applied." "WARN" Yellow
        }
    } else {
        Write-Log ".env configuration file is present." "SUCCESS" Green
    }

    # Step 3: Handle Repair or Reset if requested
    if ($Repair -or $ResetData) {
        Write-Section "STEP 3: EXECUTING RECOVERY / TEARDOWN"
        $teardownCmd = "docker compose down"
        if ($ResetData) {
            $teardownCmd += " -v"
            Write-Log "Teardown with volume removal (full database reset)..." "WARN" Yellow
        }
        $null = Invoke-VerboseCommand $teardownCmd -FailOnError $false
    } else {
        Write-Section "STEP 3: PRE-BUILD ENVIRONMENT PREPARATION"
        Write-Log "Ready to build and initialize environment." "INFO" White
    }

    # Step 4: Build Custom PostgreSQL Image
    Write-Section "STEP 4: BUILDING CUSTOM POSTGRESQL 16 + POSTGIS + PGVECTOR IMAGE"
    $buildCmd = "docker compose build"
    if ($NoCache -or $Repair) {
        Write-Log "Building Docker image with --no-cache for a completely clean installation..." "INFO" Yellow
        $buildCmd += " --no-cache"
    }
    $null = Invoke-VerboseCommand $buildCmd -FailOnError $true

    # Step 5: Launch Container Environment
    Write-Section "STEP 5: LAUNCHING DOCKER CONTAINERS"
    $null = Invoke-VerboseCommand "docker compose up -d" -FailOnError $true

    # Step 6: Wait for Healthcheck
    Write-Section "STEP 6: AWAITING DATABASE HEALTHCHECK"
    Write-Log "Waiting for database container (hyperlocal-postgres) to report healthy (max timeout: ${TimeoutSeconds}s)..." "INFO" Yellow

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
            $services = @($psResult)
            $dbService = $services | Where-Object { $_.Service -eq "db" -or $_.Name -like "*postgres*" } | Select-Object -First 1
            if ($dbService) {
                $dbStatus = $dbService.Status
                $dbHealth = $dbService.Health
            }
        }

        Write-Log "Polling after ${Elapsed}s: Status = '$dbStatus', Health = '$dbHealth'" "INFO" DarkGray

        if ($dbHealth -eq "healthy" -or $dbStatus -like "*healthy*") {
            $IsHealthy = $true
            break
        }
    }

    if (-not $IsHealthy) {
        throw "Container did not reach 'healthy' state within $TimeoutSeconds seconds. Review container logs for details."
    }
    Write-Log "Container reached HEALTHY state!" "SUCCESS" Green

    # Step 7: Automated End-to-End Verification Test Suite
    Write-Section "STEP 7: RUNNING VERIFICATION TEST SUITE"

    # Test 7.1: Verify Installed Extensions
    Write-Log "Test 1/4: Querying installed extensions..." "INFO" White
    $extQuery = 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "\dx"'
    $null = Invoke-VerboseCommand $extQuery -FailOnError $true

    # Test 7.2: PostGIS Geospatial Capability & 3km Radius Calculation
    Write-Log "Test 2/4: Verifying PostGIS spatial 3km radius calculations..." "INFO" White
    $spatialQuery = 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "SELECT PostGIS_Version(); SELECT ST_DWithin(ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326)::geography, ST_SetSRID(ST_MakePoint(77.6000, 12.9750), 4326)::geography, 3000) AS hyperlocal_3km_match;"'
    $null = Invoke-VerboseCommand $spatialQuery -FailOnError $true

    # Test 7.3: pgvector Vector Distance Calculation
    Write-Log "Test 3/4: Verifying pgvector cosine & L2 vector distance calculations..." "INFO" White
    $vectorQuery = 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "SELECT ''[1,2,3]''::vector <=> ''[1,2,3]''::vector AS cosine_dist, ''[1,2,3]''::vector <-> ''[4,5,6]''::vector AS l2_dist;"'
    $null = Invoke-VerboseCommand $vectorQuery -FailOnError $true

    # Test 7.4: uuid-ossp Generation
    Write-Log "Test 4/4: Verifying UUID generator (uuid-ossp)..." "INFO" White
    $uuidQuery = 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "SELECT uuid_generate_v4() AS test_generated_uuid;"'
    $null = Invoke-VerboseCommand $uuidQuery -FailOnError $true

    # Step 8: Initialize Core Backend Database Schema & Models
    Write-Section "STEP 8: INITIALIZING CORE BACKEND SCHEMA & TABLES"
    $schemaFile = Join-Path $WorkspaceRoot "backend\schema.sql"
    if (Test-Path $schemaFile) {
        Write-Log "Applying backend schema (users, categories, inventory_items, item_categories, requirements)..." "INFO" White
        $applySchemaCmd = "Get-Content '$schemaFile' | docker compose exec -T db psql -U postgres -d hyperlocal_marketplace"
        $null = Invoke-VerboseCommand $applySchemaCmd -FailOnError $true

        Write-Log "Verifying created tables and row counts in database..." "INFO" White
        $tableCountQuery = "docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c `"SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name;`""
        $null = Invoke-VerboseCommand $tableCountQuery -FailOnError $false
    } else {
        Write-Log "Schema file ($schemaFile) not found, skipping schema bootstrap." "WARN" Yellow
    }

    # Step 9: Capture Container Startup Logs
    Write-Section "STEP 9: CAPTURING CONTAINER LOGS"
    $null = Invoke-VerboseCommand "docker compose logs --tail=30 --no-color db" -FailOnError $false

    # Mirror to setup_latest.log
    Copy-Item -Path $LogFilePath -Destination $LatestLogPath -Force

    # Step 10: Summary & Next Steps
    Write-Section "SETUP & REPLICATION COMPLETED SUCCESSFULLY"
    Write-Log "Hyperlocal Marketplace Docker Stack is 100% OPERATIONAL!" "SUCCESS" Green
    Write-Log "" "INFO" White
    Write-Log "Database Port   : localhost:5432" "INFO" Cyan
    Write-Log "Database Name   : hyperlocal_marketplace" "INFO" Cyan
    Write-Log "Primary User    : postgres" "INFO" Cyan
    Write-Log "Connection URL  : postgresql://postgres:postgres_dev_password_change_in_prod@localhost:5432/hyperlocal_marketplace?sslmode=disable" "INFO" Cyan
    Write-Log "Setup Log File  : $LogFilePath" "INFO" Cyan
    Write-Log "Latest Log Link : $LatestLogPath" "INFO" Cyan
    Write-Log "" "INFO" White
    Write-Log "How to operate this stack:" "INFO" White
    Write-Log "  - To start: .\start.ps1" "INFO" White
    Write-Log "  - To stop : .\stop.ps1" "INFO" White
    Write-Log "  - To repair/rebuild from scratch: .\setup.ps1 -Repair -NoCache" "INFO" White
    
    exit 0
} catch {
    Write-Section "SETUP FAILED"
    Write-Log "Fatal error encountered during setup: $_" "ERROR" Red
    Write-Log "Check full trace above or in log file: $LogFilePath" "ERROR" Red
    
    if (Test-Path $LogFilePath) {
        Copy-Item -Path $LogFilePath -Destination $LatestLogPath -Force -ErrorAction SilentlyContinue
    }
    exit 1
}
