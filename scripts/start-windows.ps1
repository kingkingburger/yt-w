[CmdletBinding()]
param(
    [switch]$NoBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$helperPath = Join-Path $PSScriptRoot 'windows-recycle-helper.ps1'
$downloadRoot = Join-Path $repositoryRoot 'downloads'
$helperArguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    "`"$helperPath`"",
    '-DownloadRoot',
    "`"$downloadRoot`""
)

Start-Process -FilePath 'powershell.exe' `
    -ArgumentList $helperArguments `
    -WindowStyle Hidden

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
