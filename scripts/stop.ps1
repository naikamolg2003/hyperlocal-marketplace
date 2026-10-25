<#
.SYNOPSIS
    Hyperlocal Marketplace Docker Shutdown Script
.DESCRIPTION
    Gracefully stops and shuts down the Docker Compose environment.
    Captures all executed commands, stdout, stderr, and shutdown status
    to a timestamped log file.
.PARAMETER Volumes
    If specified, removes named volumes (WARNING: deletes persistent database data).
.PARAMETER TimeoutSeconds
    Timeout in seconds for graceful shutdown before containers are terminated (Default: 15).
.PARAMETER LogDir
    Directory path to store the shutdown logs.
.EXAMPLE
    .\scripts\stop.ps1
.EXAMPLE
    .\scripts\stop.ps1 -TimeoutSeconds 30
.EXAMPLE
    .\scripts\stop.ps1 -Volumes
#>

[CmdletBinding()]
param (
    [switch]$Volumes,
    [int]$TimeoutSeconds = 15,
    [string]$LogDir = "logs"
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
$LogFileName = "shutdown_$Timestamp.log"
$LogFilePath = Join-Path $ResolvedLogDir $LogFileName
$LatestLogPath = Join-Path $ResolvedLogDir "shutdown_latest.log"

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
    
    # Write to Console
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
    Write-Section "HYPERLOCAL MARKETPLACE - DOCKER SHUTDOWN SEQUENCE"
    Write-Log "Workspace root: $WorkspaceRoot" "INFO" DarkCyan
    Write-Log "Shutdown log destination: $LogFilePath" "INFO" DarkCyan

    # Step 1: Pre-shutdown Verification & Metrics Snapshot
    Write-Section "STEP 1: PRE-SHUTDOWN SYSTEM VERIFICATION & METRICS"
    
    # Check Docker CLI
    $dockerCheck = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCheck) {
        throw "Docker CLI was not found in PATH."
    }

    # Check if containers are currently running
    Write-Log "Inspecting current container status..." "INFO" White
    $runningCheck = Invoke-VerboseCommand "docker compose ps --services --filter status=running" -FailOnError $false
    
    $activeServices = @($runningCheck.Output | Where-Object { $_ -match "\S" })
    if ($activeServices.Count -eq 0) {
        Write-Log "No running Hyperlocal Marketplace services found. Proceeding with cleanup verification..." "INFO" Yellow
    } else {
        Write-Log "Active services found: $($activeServices -join ', ')" "INFO" Cyan

        # Pre-shutdown Resource Snapshot
        Write-Log "Capturing pre-shutdown resource metrics..." "INFO" White
        $null = Invoke-VerboseCommand 'docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"' -FailOnError $false

        # Check for active database connections that will be terminated
        Write-Log "Checking active database client connections before termination..." "INFO" White
        $null = Invoke-VerboseCommand 'docker compose exec -T db psql -U postgres -d hyperlocal_marketplace -c "SELECT state, count(*) FROM pg_stat_activity GROUP BY state;"' -FailOnError $false
    }

    # Step 2: Graceful Shutdown
    Write-Section "STEP 2: STOPPING DOCKER CONTAINERS"
    
    $composeDownCmd = "docker compose down -t $TimeoutSeconds"
    if ($Volumes) {
        Write-Log "WARNING: -Volumes switch specified! Persistent database volume will be REMOVED." "WARN" Red
        $composeDownCmd += " -v"
    }
    
    $null = Invoke-VerboseCommand $composeDownCmd -FailOnError $true

    # Step 3: Verify Post-Shutdown State & Volume Preservation
    Write-Section "STEP 3: VERIFYING POST-SHUTDOWN STATE"
    Write-Log "Verifying all containers are terminated..." "INFO" White
    $null = Invoke-VerboseCommand "docker compose ps" -FailOnError $false

    Write-Log "Checking persistent volume status..." "INFO" White
    $null = Invoke-VerboseCommand 'docker volume ls --filter "name=hyperlocal_postgres_data"' -FailOnError $false

    # Mirror to shutdown_latest.log
    Copy-Item -Path $LogFilePath -Destination $LatestLogPath -Force

    # Step 4: Summary
    Write-Section "SHUTDOWN COMPLETED"
    Write-Log "Docker environment has been stopped cleanly." "SUCCESS" Green
    Write-Log "Verbose Log     : $LogFilePath" "INFO" Cyan
    Write-Log "Latest Log Link : $LatestLogPath" "INFO" Cyan
    Write-Log "To start again  : Run .\scripts\start.ps1" "INFO" White
    
    exit 0
} catch {
    Write-Section "SHUTDOWN FAILED"
    Write-Log "Fatal error encountered during shutdown: $_" "ERROR" Red
    Write-Log "Check full trace above or in log file: $LogFilePath" "ERROR" Red
    
    if (Test-Path $LogFilePath) {
        Copy-Item -Path $LogFilePath -Destination $LatestLogPath -Force -ErrorAction SilentlyContinue
    }
    exit 1
}
