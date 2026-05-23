#!/usr/bin/env pwsh
# Reinstala/configura Docker Desktop apos mover para o SSD (ex.: D:\Docker\Docker).
# Uso: .\scripts\setup-docker.ps1

$ErrorActionPreference = 'Stop'

$DockerRoot = 'D:\Docker\Docker'
$DockerExe = Join-Path $DockerRoot 'Docker Desktop.exe'
$DockerBin = Join-Path $DockerRoot 'resources\bin'
$DockerCli = Join-Path $DockerBin 'docker.exe'
$Installer = Join-Path $DockerRoot 'Docker Desktop Installer.exe'
$WslDataRoot = 'D:\Docker\wsl-data'

Write-Host '=== Setup Docker (SSD) ===' -ForegroundColor Green

if (-not (Test-Path $DockerCli)) {
    Write-Host "Docker CLI nao encontrado em $DockerCli" -ForegroundColor Red
    Write-Host 'Ajuste `$DockerRoot` no script se a pasta for outra.' -ForegroundColor Yellow
    exit 1
}

# PATH do usuario (persistente)
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -notlike "*$DockerBin*") {
    [Environment]::SetEnvironmentVariable('Path', "$DockerBin;$userPath", 'User')
    Write-Host "PATH atualizado: $DockerBin" -ForegroundColor Cyan
}
$env:PATH = "$DockerBin;$env:PATH"
[Environment]::SetEnvironmentVariable('DOCKER_BIN', $DockerCli, 'User')
$env:DOCKER_BIN = $DockerCli

function Invoke-Docker {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & $DockerCli @Args
}

# WSL2 (necessario para Docker Desktop)
Write-Host 'Verificando WSL2...' -ForegroundColor Cyan
wsl --install --no-distribution 2>$null | Out-Null
$wslStatus = wsl --status 2>&1 | Out-String
if ($wslStatus -match 'Vers.o Padr.o:\s*2') {
    Write-Host 'WSL2 OK' -ForegroundColor DarkGray
} else {
    Write-Host 'WSL2 pode precisar de reinicio do Windows. Rode o script de novo apos reiniciar.' -ForegroundColor Yellow
}

# Instalador oficial (cria servicos e distros WSL do Docker)
if (Test-Path $Installer) {
    Write-Host 'Executando instalador do Docker (UAC)...' -ForegroundColor Cyan
  New-Item -ItemType Directory -Force -Path $WslDataRoot | Out-Null
    $installArgs = @(
        'install',
        '--accept-license',
        '--quiet',
        "--installation-dir=$DockerRoot",
        "--wsl-default-data-root=$WslDataRoot",
        '--backend=wsl-2'
    )
    $proc = Start-Process -FilePath $Installer -ArgumentList $installArgs -Verb RunAs -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Write-Host "Instalador retornou codigo $($proc.ExitCode). Abra o Docker Desktop manualmente se necessario." -ForegroundColor Yellow
    }
} else {
    Write-Host "Instalador nao encontrado; apenas iniciando Docker Desktop." -ForegroundColor Yellow
}

if (-not (Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue)) {
    Start-Process $DockerExe
    Write-Host 'Docker Desktop iniciado.' -ForegroundColor Cyan
}

Write-Host 'Aguardando daemon (ate 5 min)...' -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        Invoke-Docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            Write-Host "Docker pronto apos $($i * 5)s" -ForegroundColor Green
            break
        }
    } catch {
        # daemon ainda nao disponivel
    }
    Start-Sleep -Seconds 5
}

if (-not $ready) {
    Write-Host ''
    Write-Host 'Docker ainda nao respondeu.' -ForegroundColor Red
    Write-Host '1. Reinicie o Windows (WSL pode exigir reboot apos wsl --install)' -ForegroundColor Yellow
    Write-Host '2. Abra D:\Docker\Docker\Docker Desktop.exe e aguarde ficar verde' -ForegroundColor Yellow
    Write-Host '3. Rode: .\scripts\docker-dev.ps1' -ForegroundColor Yellow
    exit 1
}

Invoke-Docker version
Write-Host ''
Write-Host 'Docker OK. Subindo projeto...' -ForegroundColor Green
& (Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts\docker-dev.ps1')
