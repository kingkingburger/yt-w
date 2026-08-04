[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName = 'yt-w-windows-recycle-helper'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'This installer requires Windows.'
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$launcherPath = Join-Path $PSScriptRoot 'run-windows-recycle-helper-hidden.vbs'
$helperPath = Join-Path $PSScriptRoot 'windows-recycle-helper.ps1'
$downloadRoot = Join-Path $repositoryRoot 'downloads'
$wscriptPath = Join-Path $env:SystemRoot 'System32\wscript.exe'
$userName = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskPath = '\'

if (-not (Test-Path -LiteralPath $launcherPath -PathType Leaf)) {
    throw "Hidden recycle launcher does not exist: $launcherPath"
}
if (-not (Test-Path -LiteralPath $helperPath -PathType Leaf)) {
    throw "Recycle helper does not exist: $helperPath"
}
if (-not (Test-Path -LiteralPath $downloadRoot -PathType Container)) {
    throw "Download root does not exist: $downloadRoot"
}
if (-not (Test-Path -LiteralPath $wscriptPath -PathType Leaf)) {
    throw "wscript.exe does not exist: $wscriptPath"
}

$actionArguments = @(
    '//B'
    '//NoLogo'
    "`"$launcherPath`""
    '/Once'
) -join ' '
$action = New-ScheduledTaskAction `
    -Execute $wscriptPath `
    -Argument $actionArguments `
    -WorkingDirectory $repositoryRoot
$currentTime = Get-Date
$firstRunAt = $currentTime.Date.AddHours(3)
if ($firstRunAt -le $currentTime) {
    $firstRunAt = $firstRunAt.AddDays(1)
}
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At $firstRunAt
$principal = New-ScheduledTaskPrincipal `
    -UserId $userName `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

if ($PSCmdlet.ShouldProcess(
    "$taskPath$TaskName",
    "register daily for $userName"
)) {
    $existingTask = Get-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $taskPath `
        -ErrorAction SilentlyContinue
    if ($null -ne $existingTask -and $existingTask.State -eq 'Running') {
        Stop-ScheduledTask -TaskName $TaskName -TaskPath $taskPath
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            Start-Sleep -Milliseconds 250
            $existingTask = Get-ScheduledTask `
                -TaskName $TaskName `
                -TaskPath $taskPath
            if ($existingTask.State -ne 'Running') {
                break
            }
        }
    }

    Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $taskPath `
        -Action $action `
        -Trigger $dailyTrigger `
        -Principal $principal `
        -Settings $settings `
        -Description 'Checks yt-w recycle requests daily at 03:00 in the current user session.' `
        -Force | Out-Null
    Write-Host "Registered daily Scheduled Task: $taskPath$TaskName"
}
