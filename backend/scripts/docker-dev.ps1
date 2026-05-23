#!/usr/bin/env pwsh
# Sobe API + Redis no Docker, aplica migrations e seed (primeira vez).
# Uso: .\scripts\docker-dev.ps1

$ErrorActionPreference = 'Stop'
$BackendRoot = Split-Path $PSScriptRoot -Parent
Set-Location $BackendRoot

Write-Host 'TM Transportadora - Docker (dev)' -ForegroundColor Green

if (-not (Test-Path '.env')) {
    Write-Host '.env nao encontrado. Copiando de .env.example...' -ForegroundColor Yellow
    Copy-Item '.env.example' '.env'
    Write-Host 'Edite backend\.env (DATABASE_URL do Supabase) e rode o script de novo.' -ForegroundColor Red
    exit 1
}

Write-Host 'Verificando Docker...' -ForegroundColor Cyan
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Docker nao esta rodando. Abra o Docker Desktop e tente novamente.' -ForegroundColor Red
    exit 1
}

Write-Host 'Build e start: api + redis...' -ForegroundColor Cyan
docker compose up -d --build api redis
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host 'Aguardando API ficar pronta...' -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $ready) {
    Write-Host 'API ainda nao respondeu. Veja os logs: docker compose logs -f api' -ForegroundColor Yellow
}

Write-Host 'Migrations...' -ForegroundColor Cyan
docker compose exec -T api alembic upgrade head
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host 'Seed (admin inicial)...' -ForegroundColor Cyan
docker compose exec -T api python scripts/seed.py

Write-Host ''
Write-Host 'Pronto!' -ForegroundColor Green
Write-Host '  Docs:   http://localhost:8000/docs'
Write-Host '  Health: http://localhost:8000/health'
Write-Host '  Logs:   docker compose logs -f api'
Write-Host '  Parar:  docker compose down'
Write-Host ''
Write-Host 'Login seed: admin@tmtransportadora.com.br / Admin@123!' -ForegroundColor DarkGray
