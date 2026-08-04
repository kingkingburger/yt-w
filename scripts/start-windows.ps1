[CmdletBinding()]
param(
    [switch]$NoBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$launcherPath = Join-Path $PSScriptRoot 'run-windows-recycle-helper-hidden.vbs'
$wscriptPath = Join-Path $env:SystemRoot 'System32\wscript.exe'
$helperTaskName = 'yt-w-windows-recycle-helper'
$helperTaskPath = '\'
$launcherArguments = @(
    '//B',
    '//NoLogo',
    "`"$launcherPath`""
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
    Start-Process -FilePath $wscriptPath `
        -ArgumentList $launcherArguments `
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
