#!/usr/bin/env pwsh
# Instala dependências do backend no venv da raiz do repo (sem Poetry).
$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path $PSScriptRoot -Parent
$VenvPython = Join-Path $BackendRoot "..\venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Crie o venv na raiz: python -m venv venv" -ForegroundColor Red
    exit 1
}

Write-Host "Installing backend package into venv..." -ForegroundColor Cyan
& $VenvPython -m pip install -e $BackendRoot
Write-Host "Done." -ForegroundColor Green
