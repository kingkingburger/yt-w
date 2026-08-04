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
$helperPath = Join-Path $PSScriptRoot 'windows-recycle-helper.ps1'
$downloadRoot = Join-Path $repositoryRoot 'downloads'
$powerShellPath = (Get-Command 'powershell.exe' -ErrorAction Stop).Source
$userName = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskPath = '\'

if (-not (Test-Path -LiteralPath $helperPath -PathType Leaf)) {
    throw "Recycle helper does not exist: $helperPath"
}
if (-not (Test-Path -LiteralPath $downloadRoot -PathType Container)) {
    throw "Download root does not exist: $downloadRoot"
}

$actionArguments = @(
    '-NoProfile'
    '-ExecutionPolicy Bypass'
    '-WindowStyle Hidden'
    "-File `"$helperPath`""
    "-DownloadRoot `"$downloadRoot`""
    '-Once'
) -join ' '
$action = New-ScheduledTaskAction `
    -Execute $powerShellPath `
    -Argument $actionArguments `
    -WorkingDirectory $repositoryRoot
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $userName
$pollTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 1)
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
    "register for $userName and start"
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
        -Trigger @($logonTrigger, $pollTrigger) `
        -Principal $principal `
        -Settings $settings `
        -Description 'Checks yt-w recycle requests every minute in the current user session.' `
        -Force | Out-Null
    Start-ScheduledTask -TaskName $TaskName -TaskPath $taskPath
    Write-Host "Registered and started Scheduled Task: $taskPath$TaskName"
}
