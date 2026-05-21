#!/usr/bin/env pwsh
# Development startup script for Windows

Write-Host "Starting TM Transportadora Backend (Development)" -ForegroundColor Green

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host ".env not found. Copying from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "Please edit .env with your settings before continuing." -ForegroundColor Red
    exit 1
}

# Run migrations
Write-Host "Running database migrations..." -ForegroundColor Cyan
poetry run alembic upgrade head

# Seed database
Write-Host "Seeding database..." -ForegroundColor Cyan
poetry run python scripts/seed.py

# Start the server
Write-Host "Starting API server..." -ForegroundColor Green
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
