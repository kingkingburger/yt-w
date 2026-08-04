[CmdletBinding()]
param(
    [switch]$NoBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$helperPath = Join-Path $PSScriptRoot 'windows-recycle-helper.ps1'
$downloadRoot = Join-Path $repositoryRoot 'downloads'
$helperTaskName = 'yt-w-windows-recycle-helper'
$helperTaskPath = '\'
$helperArguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    "`"$helperPath`"",
    '-DownloadRoot',
    "`"$downloadRoot`""
)

$helperTask = Get-ScheduledTask `
    -TaskName $helperTaskName `
    -TaskPath $helperTaskPath `
    -ErrorAction SilentlyContinue
if ($null -ne $helperTask -and $helperTask.State -ne 'Disabled') {
    if ($helperTask.State -ne 'Running') {
        Start-ScheduledTask `
            -TaskName $helperTaskName `
            -TaskPath $helperTaskPath
    }
}
else {
    Write-Warning (
        'Windows recycle Scheduled Task is not installed or is disabled. ' +
        'Run .\scripts\install-windows-recycle-task.ps1 once.'
    )
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList $helperArguments `
        -WindowStyle Hidden
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
