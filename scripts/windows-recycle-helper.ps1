[CmdletBinding()]
param(
    [string]$DownloadRoot = (Join-Path $PSScriptRoot '..\downloads'),
    [ValidateRange(1, 3600)]
    [int]$PollIntervalSeconds = 5,
    [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'This helper requires Windows.'
}

$resolvedDownloadRoot = [IO.Path]::GetFullPath($DownloadRoot)
if (-not (Test-Path -LiteralPath $resolvedDownloadRoot -PathType Container)) {
    throw "Download root does not exist: $resolvedDownloadRoot"
}

$requestDirectory = Join-Path $resolvedDownloadRoot '.recycle-requests'
$logDirectory = Join-Path (Split-Path -Parent $resolvedDownloadRoot) 'logs'
$logPath = Join-Path $logDirectory 'windows-recycle-helper.log'
New-Item -ItemType Directory -Path $requestDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

function Write-HelperLog {
    param([Parameter(Mandatory)][string]$Message)

    $line = '{0} - {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding utf8
    Write-Host $line
}

function Resolve-ContainedPath {
    param(
        [Parameter(Mandatory)][string]$RelativePath,
        [Parameter(Mandatory)][string]$RequiredTopDirectory
    )

    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        throw 'Recycle request contains an empty path.'
    }

    $normalized = $RelativePath.Replace(
        [IO.Path]::AltDirectorySeparatorChar,
        [IO.Path]::DirectorySeparatorChar
    )
    if ([IO.Path]::IsPathRooted($normalized)) {
        throw "Recycle request contains an absolute path: $RelativePath"
    }
    $segments = $normalized.Split(
        [IO.Path]::DirectorySeparatorChar,
        [StringSplitOptions]::RemoveEmptyEntries
    )
    if (
        $segments.Count -eq 0 -or
        -not $segments[0].Equals(
            $RequiredTopDirectory,
            [StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw (
            "Recycle request path must be under " +
            "$RequiredTopDirectory/: $RelativePath"
        )
    }

    $candidate = [IO.Path]::GetFullPath(
        (Join-Path $resolvedDownloadRoot $normalized)
    )
    $trimCharacters = @(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    $rootPrefix = $resolvedDownloadRoot.TrimEnd($trimCharacters) +
        [IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith(
        $rootPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Recycle request escapes the download root: $RelativePath"
    }

    return $candidate
}

Add-Type -AssemblyName Microsoft.VisualBasic

$lockPath = Join-Path $requestDirectory '.helper.lock'
try {
    $lockStream = [IO.File]::Open(
        $lockPath,
        [IO.FileMode]::OpenOrCreate,
        [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None
    )
}
catch {
    Write-HelperLog 'Another Windows recycle helper is already running.'
    exit 0
}

try {
    if (-not $Once) {
        Write-HelperLog "Watching recycle requests in $requestDirectory"
    }

    do {
        $hadFailure = $false
        $requestFiles = @(
            Get-ChildItem -LiteralPath $requestDirectory `
                -File -Filter '*.json' | Sort-Object Name
        )
        if ($Once -and $requestFiles.Count -gt 0) {
            Write-HelperLog (
                "Processing $($requestFiles.Count) recycle request(s)"
            )
        }

        foreach ($requestFile in $requestFiles) {
            try {
                $request = Get-Content -LiteralPath $requestFile.FullName `
                    -Raw -Encoding utf8 | ConvertFrom-Json
                if ($request.schema_version -ne 1) {
                    throw "Unsupported schema version: $($request.schema_version)"
                }

                $outputPath = Resolve-ContainedPath `
                    -RelativePath ([string]$request.output) `
                    -RequiredTopDirectory 'merged'
                if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
                    throw "Merged output does not exist: $outputPath"
                }

                $sourcePaths = @($request.files)
                if ($sourcePaths.Count -eq 0) {
                    throw 'Recycle request contains no source files.'
                }

                foreach ($relativeSourcePath in $sourcePaths) {
                    $sourcePath = Resolve-ContainedPath `
                        -RelativePath ([string]$relativeSourcePath) `
                        -RequiredTopDirectory 'live'
                    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
                        continue
                    }

                    [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
                        $sourcePath,
                        [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
                        [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin,
                        [Microsoft.VisualBasic.FileIO.UICancelOption]::ThrowException
                    )
                    if (Test-Path -LiteralPath $sourcePath) {
                        throw "Source file still exists after recycle: $sourcePath"
                    }
                }

                Remove-Item -LiteralPath $requestFile.FullName
                Write-HelperLog "Completed recycle request: $($requestFile.Name)"
            }
            catch {
                $hadFailure = $true
                Write-HelperLog (
                    "Failed recycle request $($requestFile.Name): $($_.Exception.Message)"
                )
            }
        }

        if (-not $Once) {
            Start-Sleep -Seconds $PollIntervalSeconds
        }
    } while (-not $Once)

    if ($hadFailure) {
        exit 1
    }
}
finally {
    $lockStream.Dispose()
}
