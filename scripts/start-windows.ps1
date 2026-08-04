[CmdletBinding()]
param(
    [switch]$NoBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$helperTaskName = 'yt-w-windows-recycle-helper'
$helperTaskPath = '\'

$helperTask = Get-ScheduledTask `
    -TaskName $helperTaskName `
    -TaskPath $helperTaskPath `
    -ErrorAction SilentlyContinue
if ($null -eq $helperTask -or $helperTask.State -eq 'Disabled') {
    Write-Warning (
        'Windows recycle Scheduled Task is not installed or is disabled. ' +
        'Run .\scripts\install-windows-recycle-task.ps1 once.'
    )
}

Push-Location $repositoryRoot
try {
    if ($NoBuild) {
        docker compose up -d
    }
    else {
        docker compose up -d --build
    }
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
