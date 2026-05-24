#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs GenericRagGenerator as a Windows service via NSSM.

.DESCRIPTION
    Wraps `uvicorn app.main:app` from the project's .venv as an auto-starting
    Windows service. Captures stdout/stderr into rotated logs under .\logs\
    and restarts the process on failure with a 5 s delay.

.NOTES
    Requires NSSM (https://nssm.cc) on PATH. Install via one of:
        winget install NSSM.NSSM
        choco install nssm
        Manual: drop nssm.exe in a directory on PATH.
#>
[CmdletBinding()]
param(
    [string]$ServiceName = 'GenericRagGenerator',
    [string]$BindHost    = '127.0.0.1',
    [int]   $Port        = 8000
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
