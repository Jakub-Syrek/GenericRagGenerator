#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Stops and removes the GenericRagGenerator Windows service.
#>
[CmdletBinding()]
param(
    [string]$ServiceName = 'GenericRagGenerator'
)

$ErrorActionPreference = 'Stop'

$NssmCmd = Get-Command nssm.exe -ErrorAction SilentlyContinue
if (-not $NssmCmd) {
    throw "NSSM not found on PATH. Install it (winget install NSSM.NSSM) and re-run."
}
$Nssm = $NssmCmd.Source

if (-not (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) {
    Write-Host "Service '$ServiceName' is not registered; nothing to do."
    return
}

Write-Host "Stopping service '$ServiceName'..."
& $Nssm stop $ServiceName | Out-Null
Start-Sleep -Seconds 2

Write-Host "Removing service '$ServiceName'..."
& $Nssm remove $ServiceName confirm | Out-Null

Write-Host "Service '$ServiceName' removed."
