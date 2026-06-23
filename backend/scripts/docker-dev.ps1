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

$dockerBin = $env:DOCKER_BIN
if (-not $dockerBin) {
    $candidates = @(
        'D:\Docker\Docker\resources\bin\docker.exe',
        "${env:ProgramFiles}\Docker\Docker\resources\bin\docker.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $dockerBin = $c; break }
    }
}
if ($dockerBin) {
    $dockerDir = Split-Path $dockerBin -Parent
    $env:PATH = "$dockerDir;$env:PATH"
}

function Invoke-Docker {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    if ($dockerBin) { & $dockerBin @Args } else { & docker @Args }
}

function Test-DockerDaemon {
    try {
        Invoke-Docker info *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Start-DockerDesktopIfNeeded {
    $desktop = 'D:\Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $desktop)) {
        $desktop = "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe"
    }
    if (-not (Test-Path $desktop)) { return }

    if (-not (Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue)) {
        Write-Host 'Iniciando Docker Desktop...' -ForegroundColor Yellow
        Start-Process $desktop | Out-Null
    }
}

Write-Host 'Verificando Docker...' -ForegroundColor Cyan
$rebootPending = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' `
    -Name PendingFileRenameOperations -ErrorAction SilentlyContinue
if ($rebootPending -and $rebootPending.PendingFileRenameOperations) {
    Write-Host 'Aviso: Windows marcou reinicio pendente (atualizacoes/WSL).' -ForegroundColor Yellow
    Write-Host 'Se o Docker abaixo responder OK, pode continuar sem reiniciar o PC.' -ForegroundColor DarkGray
}

if (-not (Test-DockerDaemon)) {
    Start-DockerDesktopIfNeeded
    $ready = $false
    for ($i = 0; $i -lt 36; $i++) {
        if (Test-DockerDaemon) {
            $ready = $true
            Write-Host "Docker pronto apos $($i * 5)s" -ForegroundColor DarkGray
            break
        }
        if ($i -eq 0) { Write-Host 'Aguardando Docker Desktop (ate 3 min)...' -ForegroundColor Yellow }
        Start-Sleep -Seconds 5
    }
    if (-not $ready) {
        Write-Host 'Docker nao esta rodando.' -ForegroundColor Red
        Write-Host '  1. Abra D:\Docker\Docker\Docker Desktop.exe e aguarde ficar verde' -ForegroundColor Yellow
        Write-Host '  2. Se WSL estiver vazio, rode: .\scripts\setup-docker.ps1' -ForegroundColor Yellow
        Write-Host '  3. Pode ser necessario reiniciar o Windows apos instalar o WSL2' -ForegroundColor Yellow
        exit 1
    }
}

Write-Host 'Build e start: api + redis...' -ForegroundColor Cyan
Invoke-Docker compose up -d --build api redis
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
Invoke-Docker compose exec -T api alembic upgrade head
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host 'Seed (admin inicial)...' -ForegroundColor Cyan
Invoke-Docker compose exec -T api python scripts/seed.py

Write-Host ''
Write-Host 'Pronto!' -ForegroundColor Green
Write-Host '  Docs:   http://localhost:8000/docs'
Write-Host '  Health: http://localhost:8000/health'
Write-Host '  Logs:   docker compose logs -f api'
Write-Host '  Parar:  docker compose down'
Write-Host ''
Write-Host 'Login seed: admin@tmtransportadora.com.br / Admin@123!' -ForegroundColor DarkGray
