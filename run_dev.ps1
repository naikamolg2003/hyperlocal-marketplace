# -----------------------------------------------------------------------------
# Hyperlocal Marketplace - Single-Command Developer Orchestration Script
# Spins up Docker PostgreSQL with PostGIS, runs DB initialization, launches
# FastAPI backend (port 8000), Vite web frontend (port 3000), and mobile interface.
# -----------------------------------------------------------------------------

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  Hyperlocal Marketplace - Developer Stack Orchestrator" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Check Docker Daemon and Container
Write-Host "`n[1/4] Verifying PostgreSQL PostGIS container..." -ForegroundColor Yellow
$DockerRunning = $false
try {
    $null = docker info 2>&1
    $DockerRunning = $true
} catch {
    $DockerRunning = $false
}

if (-not $DockerRunning) {
    Write-Host " [ERROR] Docker daemon is not running. Please start Docker Desktop/Engine." -ForegroundColor Red
    exit 1
}

$ContainerStatus = docker inspect --format '{{.State.Status}}' hyperlocal-postgres 2>$null
if ($ContainerStatus -ne "running") {
    Write-Host " Starting PostgreSQL container (hyperlocal-postgres)..." -ForegroundColor Gray
    docker compose up -d
} else {
    Write-Host " PostgreSQL container is already running." -ForegroundColor Green
}

# Wait for DB readiness
Write-Host " Waiting for PostgreSQL engine to accept connections..." -ForegroundColor Gray
$DbReady = $false
for ($i = 0; $i -lt 15; $i++) {
    $check = docker exec hyperlocal-postgres pg_isready -U postgres -d hyperlocal_marketplace 2>$null
    if ($LASTEXITCODE -eq 0) {
        $DbReady = $true
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $DbReady) {
    Write-Host " [WARNING] Database ping did not return 0 immediately. Proceeding with caution..." -ForegroundColor Yellow
} else {
    Write-Host " PostgreSQL + PostGIS + pgvector engine is HEALTHY." -ForegroundColor Green
}

# 2. Database Schema Initialization & Migrations
Write-Host "`n[2/4] Initializing database schema & extensions..." -ForegroundColor Yellow
$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

$env:PYTHONPATH = $ScriptDir
& $PythonExe -m backend.init_db
if ($LASTEXITCODE -ne 0) {
    Write-Host " [ERROR] Database initialization failed." -ForegroundColor Red
    exit 1
}
Write-Host " Database tables and PostGIS spatial columns verified." -ForegroundColor Green

# 3. Launching Services Concurrently
Write-Host "`n[3/4] Launching Services Concurrently..." -ForegroundColor Yellow
Write-Host " - FastAPI Backend: http://localhost:8000 (Docs: http://localhost:8000/docs)" -ForegroundColor Gray
Write-Host " - React Web Portal: http://localhost:3000" -ForegroundColor Gray
Write-Host " - Press Ctrl+C in this console to terminate all background servers." -ForegroundColor Yellow

$RunningProcesses = @()

# Start Backend Process
$BackendJob = Start-Process -FilePath $PythonExe -ArgumentList "-m", "uvicorn", "backend.main:app", "--port", "8000", "--reload" -PassThru -NoNewWindow
$RunningProcesses += $BackendJob

# Start Web Frontend Process
$NpmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $NpmCmd) { $NpmCmd = "npm" }
$WebFrontendJob = Start-Process -FilePath $NpmCmd -ArgumentList "run", "dev", "--", "--host", "--port", "3000" -WorkingDirectory (Join-Path $ScriptDir "frontend-web") -PassThru -NoNewWindow
$RunningProcesses += $WebFrontendJob

Write-Host "`n[4/4] All developer servers running! Monitor logs below:" -ForegroundColor Green
Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan

# Cleanup trap on Ctrl+C or script termination
try {
    while ($true) {
        Start-Sleep -Seconds 2
        # Check if backend or frontend process exited unexpectedly
        if ($BackendJob.HasExited) {
            Write-Host "Backend process exited with code $($BackendJob.ExitCode)." -ForegroundColor Red
            break
        }
        if ($WebFrontendJob.HasExited) {
            Write-Host "Frontend web process exited with code $($WebFrontendJob.ExitCode)." -ForegroundColor Red
            break
        }
    }
} finally {
    Write-Host "`nShutting down developer processes..." -ForegroundColor Yellow
    foreach ($proc in $RunningProcesses) {
        if ($proc -and -not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Developer processes stopped cleanly." -ForegroundColor Green
}
