#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs GenericRagGenerator as a Windows service via NSSM.

.DESCRIPTION
    Wraps `uvicorn app.main:app` from the project's .venv as an auto-starting
    Windows service. Captures stdout/stderr into rotated logs under .\logs\
    and restarts the process on failure with a 5 s delay.

    Two install profiles via -Mode:
      local   (default) - bind to 127.0.0.1; API reachable only from the
                          same host. Safe for personal / single-tenant use.
      public            - bind to 0.0.0.0; API reachable from the network.
                          Requires API_KEY (or AUTH_PASSWORD + JWT_SECRET)
                          in .env; the script refuses to install otherwise.

    -DisableDocs additionally sets DOCS_ENABLED=false in the service
    environment so /docs, /redoc and /openapi.json are hidden in prod.

.NOTES
    Requires NSSM (https://nssm.cc) on PATH. Install via one of:
        winget install NSSM.NSSM
        choco install nssm
        Manual: drop nssm.exe in a directory on PATH.
#>
[CmdletBinding()]
param(
    [string]$ServiceName = 'GenericRagGenerator',
    [string]$BindHost    = '',
    [int]   $Port        = 8000,
    [ValidateSet('local', 'public')]
    [string]$Mode        = 'local',
    [switch]$DisableDocs
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe   = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Backend     = Join-Path $ProjectRoot 'backend'
$LogDir      = Join-Path $ProjectRoot 'logs'
$DisplayName = 'GenericRagGenerator RAG'
$Description = 'Local Retrieval-Augmented Generation API (FastAPI + Ollama + ChromaDB).'

if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found at '$PythonExe'. Run 'python -m venv .venv' and install dependencies first."
}

# Resolve the bind address from -Mode unless the caller passed -BindHost explicitly.
if (-not $BindHost) {
    $BindHost = if ($Mode -eq 'public') { '0.0.0.0' } else { '127.0.0.1' }
}

# Refuse to expose the API publicly without any form of authentication.
if ($Mode -eq 'public') {
    $envFile = Join-Path $ProjectRoot '.env'
    $envText = if (Test-Path $envFile) { Get-Content $envFile -Raw } else { '' }
    $hasApiKey   = $envText -match '(?m)^\s*API_KEY\s*=\s*\S'
    $hasJwt      = ($envText -match '(?m)^\s*AUTH_PASSWORD\s*=\s*\S') -and ($envText -match '(?m)^\s*JWT_SECRET\s*=\s*\S')
    if (-not ($hasApiKey -or $hasJwt)) {
        throw "Refusing to expose '$ServiceName' publicly without auth. Set API_KEY (or AUTH_PASSWORD + JWT_SECRET) in $envFile before re-running with -Mode public."
    }
    Write-Host "Public mode: binding 0.0.0.0:$Port - auth detected in .env, proceeding."
}

$NssmCmd = Get-Command nssm.exe -ErrorAction SilentlyContinue
if (-not $NssmCmd) {
    throw "NSSM not found on PATH. Install it (winget install NSSM.NSSM) and re-run."
}
$Nssm = $NssmCmd.Source

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Service '$ServiceName' already exists; remove it first with .\scripts\uninstall-windows-service.ps1."
    return
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$AppArgs = "-m uvicorn app.main:app --host $BindHost --port $Port --app-dir `"$Backend`""

Write-Host "Registering service '$ServiceName'..."
& $Nssm install   $ServiceName $PythonExe $AppArgs | Out-Null
& $Nssm set       $ServiceName DisplayName                  $DisplayName                                       | Out-Null
& $Nssm set       $ServiceName Description                  $Description                                       | Out-Null
& $Nssm set       $ServiceName AppDirectory                 $ProjectRoot                                       | Out-Null
& $Nssm set       $ServiceName Start                        SERVICE_AUTO_START                                 | Out-Null
if ($DisableDocs) {
    & $Nssm set   $ServiceName AppEnvironmentExtra          "DOCS_ENABLED=false"                              | Out-Null
    Write-Host "Swagger / Redoc / OpenAPI hidden (DOCS_ENABLED=false)."
}
& $Nssm set       $ServiceName AppStdout                    (Join-Path $LogDir 'service-stdout.log')           | Out-Null
& $Nssm set       $ServiceName AppStderr                    (Join-Path $LogDir 'service-stderr.log')           | Out-Null
& $Nssm set       $ServiceName AppRotateFiles               1                                                  | Out-Null
& $Nssm set       $ServiceName AppRotateOnline              1                                                  | Out-Null
& $Nssm set       $ServiceName AppRotateBytes               10485760                                           | Out-Null
& $Nssm set       $ServiceName AppRestartDelay              5000                                               | Out-Null
& $Nssm set       $ServiceName AppStopMethodConsole         15000                                              | Out-Null

Write-Host "Starting service..."
& $Nssm start $ServiceName | Out-Null

Start-Sleep -Seconds 2
$state = (Get-Service -Name $ServiceName).Status
Write-Host "Service '$ServiceName' is now: $state"
Write-Host "Health probe: http://$BindHost:$Port/api/health"
Write-Host "Logs:         $LogDir"
