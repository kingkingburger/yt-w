[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
param(
    [string]$TaskName = 'yt-w-windows-recycle-helper'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$taskPath = '\'
$task = Get-ScheduledTask `
    -TaskName $TaskName `
    -TaskPath $taskPath `
    -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Host "Scheduled Task is not installed: $taskPath$TaskName"
    exit 0
}

if ($PSCmdlet.ShouldProcess("$taskPath$TaskName", 'stop and unregister')) {
    if ($task.State -eq 'Running') {
        Stop-ScheduledTask -TaskName $TaskName -TaskPath $taskPath
    }
    Unregister-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $taskPath `
        -Confirm:$false
    Write-Host "Unregistered Scheduled Task: $taskPath$TaskName"
}
