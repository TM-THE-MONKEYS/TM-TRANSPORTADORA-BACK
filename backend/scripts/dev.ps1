#!/usr/bin/env pwsh
# Development startup script for Windows

$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path $PSScriptRoot -Parent
Set-Location $BackendRoot

Write-Host "Starting TM Transportadora Backend (Development)" -ForegroundColor Green

function Get-DevPython {
    if (Get-Command poetry -ErrorAction SilentlyContinue) {
        return @{ Mode = "poetry" }
    }
    $venvPython = Join-Path $BackendRoot "..\venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return @{ Mode = "venv"; Python = (Resolve-Path $venvPython).Path }
    }
    throw "Poetry not found and venv missing. From repo root: python -m venv venv; then pip install -e backend (or poetry install in backend)."
}

function Invoke-Dev {
    param([string[]]$Args)
    $ctx = Get-DevPython
    if ($ctx.Mode -eq "poetry") {
        & poetry run @Args
    } else {
        & $ctx.Python @Args
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host ".env not found. Copying from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "Please edit .env with your settings before continuing." -ForegroundColor Red
    exit 1
}

$ctx = Get-DevPython
Write-Host "Using: $($ctx.Mode)" -ForegroundColor Cyan

# Run migrations
Write-Host "Running database migrations..." -ForegroundColor Cyan
if ($ctx.Mode -eq "poetry") {
    Invoke-Dev "alembic", "upgrade", "head"
} else {
    Invoke-Dev "-m", "alembic", "upgrade", "head"
}

# Seed database
Write-Host "Seeding database..." -ForegroundColor Cyan
Invoke-Dev "scripts/seed.py"

# Start the server
Write-Host "Starting API server..." -ForegroundColor Green
if ($ctx.Mode -eq "poetry") {
    Invoke-Dev "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"
} else {
    Invoke-Dev "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"
}
