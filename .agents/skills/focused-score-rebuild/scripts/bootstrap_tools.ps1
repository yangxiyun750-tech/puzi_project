[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Download', 'Install', 'Verify')]
    [string]$Action = 'Plan',
    [string]$ManifestPath = '',
    [string]$ProjectRoot = '',
    [string]$CacheDir = '',
    [string]$InstallDir = '',
    [string]$OfflineBundle = '',
    [string[]]$Tool = @(),
    [switch]$AllowOfficialFallback,
    [switch]$ApproveDownload,
    [switch]$ApproveInstall,
    [switch]$WriteLocalConfig
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$skillRoot = Split-Path -Parent $PSScriptRoot
if (-not $ManifestPath) {
    $ManifestPath = Join-Path $skillRoot 'assets\windows-toolchain-manifest.json'
}
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $skillRoot))
}
$ProjectRoot = [IO.Path]::GetFullPath($ProjectRoot)
if (-not $CacheDir) { $CacheDir = Join-Path $ProjectRoot '.tools\downloads' }
if (-not $InstallDir) { $InstallDir = Join-Path $ProjectRoot '.tools\apps' }
$CacheDir = [IO.Path]::GetFullPath($CacheDir)
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
$localConfigPath = Join-Path $ProjectRoot '.score-rebuild\toolchain-paths.json'

function Write-Result {
    param([string]$Status, [string]$Id, [string]$Detail)
    Write-Output ('[{0}] {1}: {2}' -f $Status, $Id, $Detail)
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing JSON file: $Path"
    }
    try {
        return Get-Content -Raw -LiteralPath $Path -Encoding UTF8 | ConvertFrom-Json
    } catch {
        throw "Invalid JSON file ${Path}: $($_.Exception.Message)"
    }
}

function Read-LocalConfig {
    $result = @{}
    if (-not (Test-Path -LiteralPath $localConfigPath -PathType Leaf)) { return $result }
    $payload = Read-JsonFile $localConfigPath
    foreach ($property in $payload.PSObject.Properties) {
        if ($property.Value -is [string] -and $property.Value) {
            $result[$property.Name] = $property.Value
        }
    }
    return $result
}

function Save-LocalConfig {
    param([hashtable]$Config)
    $directory = Split-Path -Parent $localConfigPath
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $temporary = Join-Path $directory ('.toolchain-paths.{0}.tmp' -f [Guid]::NewGuid().ToString('N'))
    try {
        $Config | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $localConfigPath -Force
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}

function Expand-ToolPath {
    param([string]$Value, $ToolSpec)
    $tokens = @{
        '{PROGRAMFILES}' = [string]$env:ProgramFiles
        '{PROGRAMFILES_X86}' = [string]${env:ProgramFiles(x86)}
        '{LOCALAPPDATA}' = [string]$env:LOCALAPPDATA
        '{PROJECT_ROOT}' = $ProjectRoot
        '{INSTALL_ROOT}' = $InstallDir
        '{VERSION}' = [string]$ToolSpec.version
    }
    $expanded = [Environment]::ExpandEnvironmentVariables($Value)
    foreach ($item in $tokens.GetEnumerator()) {
        if ($expanded.Contains($item.Key)) {
            if (-not $item.Value) { return $null }
            $expanded = $expanded.Replace($item.Key, $item.Value)
        }
    }
    return [IO.Path]::GetFullPath(($expanded -replace '/', [IO.Path]::DirectorySeparatorChar))
}

function Find-Executable {
    param($ToolSpec, [hashtable]$LocalConfig)
    $overrideName = [string]$ToolSpec.override_env
    $override = [Environment]::GetEnvironmentVariable($overrideName)
    if ($override -and (Test-Path -LiteralPath $override -PathType Leaf)) {
        return [IO.Path]::GetFullPath($override)
    }
    if ($LocalConfig.ContainsKey($overrideName)) {
        $configured = [string]$LocalConfig[$overrideName]
        if (Test-Path -LiteralPath $configured -PathType Leaf) {
            return [IO.Path]::GetFullPath($configured)
        }
    }
    foreach ($name in $ToolSpec.detect.command_names) {
        $command = Get-Command ([string]$name) -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command -and $command.Source -and (Test-Path -LiteralPath $command.Source -PathType Leaf)) {
            return [IO.Path]::GetFullPath($command.Source)
        }
    }
    foreach ($template in $ToolSpec.detect.candidate_paths) {
        $candidate = Expand-ToolPath ([string]$template) $ToolSpec
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $candidate
        }
    }
    return $null
}

function Test-Executable {
    param($ToolSpec, [string]$Executable)
    if (-not $Executable) {
        return [pscustomobject]@{ Ok = $false; Version = ''; Detail = 'not found' }
    }
    try {
        $arguments = @($ToolSpec.detect.version_args | ForEach-Object { [string]$_ })
        $output = (& $Executable @arguments 2>&1 | Out-String).Trim()
        $nativeCode = $LASTEXITCODE
        $pattern = [string]$ToolSpec.detect.version_pattern
        $matched = $output -match $pattern
        return [pscustomobject]@{
            Ok = ($nativeCode -eq 0 -or $matched) -and $matched
            Version = (($output -split "`r?`n" | Where-Object { $_ }) | Select-Object -First 1)
            Detail = "exit=$nativeCode pattern=$pattern"
        }
    } catch {
        return [pscustomobject]@{ Ok = $false; Version = ''; Detail = $_.Exception.Message }
    }
}

function Get-SelectedTools {
    param($Manifest)
    $all = @($Manifest.tools)
    if (-not $Tool -or $Tool.Count -eq 0) { return $all }
    $known = @{}
    foreach ($item in $all) { $known[[string]$item.id] = $item }
    $selected = @()
    foreach ($id in $Tool) {
        if (-not $known.ContainsKey($id)) { throw "Unknown tool id: $id" }
        $selected += $known[$id]
    }
    return $selected
}

function Test-PackageMetadata {
    param($ToolSpec)
    $package = $ToolSpec.package
    if ([string]$package.source_status -ne 'ready') {
        return "source_status=$($package.source_status)"
    }
    if (-not $package.filename) { return 'filename is not configured' }
    if (-not ([string]$package.sha256 -match '^[0-9a-fA-F]{64}$')) {
        return 'sha256 is not a 64-character hexadecimal digest'
    }
    return ''
}

function Test-PackageHash {
    param([string]$Path, [string]$Expected)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    return $actual -eq $Expected.ToLowerInvariant()
}

function Get-PackagePath {
    param($ToolSpec)
    return Join-Path $CacheDir ([string]$ToolSpec.package.filename)
}

function Download-Package {
    param($ToolSpec)
    $metadataError = Test-PackageMetadata $ToolSpec
    if ($metadataError) {
        Write-Result 'PENDING_MIRROR' ([string]$ToolSpec.id) $metadataError
        return $false
    }
    New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
    $destination = Get-PackagePath $ToolSpec
    $expected = [string]$ToolSpec.package.sha256
    if (Test-PackageHash $destination $expected) {
        Write-Result 'PASS' ([string]$ToolSpec.id) "verified cache $destination"
        return $true
    }
    if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Force }

    $sources = @()
    if ($OfflineBundle) {
        $offlinePath = Join-Path ([IO.Path]::GetFullPath($OfflineBundle)) ([string]$ToolSpec.package.filename)
        if (Test-Path -LiteralPath $offlinePath -PathType Leaf) { $sources += $offlinePath }
    }
    foreach ($url in $ToolSpec.package.domestic_urls) {
        if ($url) { $sources += [string]$url }
    }
    if ($AllowOfficialFallback -and $ToolSpec.package.official_url) {
        $sources += [string]$ToolSpec.package.official_url
    }
    if ($sources.Count -eq 0) {
        Write-Result 'SOURCE_UNAVAILABLE' ([string]$ToolSpec.id) 'no approved offline file or allowed URL'
        return $false
    }

    foreach ($source in $sources) {
        $partial = "$destination.partial"
        if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
        try {
            if (Test-Path -LiteralPath $source -PathType Leaf) {
                Copy-Item -LiteralPath $source -Destination $partial
            } else {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -UseBasicParsing -Uri $source -OutFile $partial
            }
            if (-not (Test-PackageHash $partial $expected)) {
                Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
                throw "HASH_MISMATCH for $($ToolSpec.id) from $source"
            }
            Move-Item -LiteralPath $partial -Destination $destination -Force
            Write-Result 'PASS' ([string]$ToolSpec.id) "downloaded and verified $destination"
            return $true
        } catch {
            Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
            if ($_.Exception.Message -like 'HASH_MISMATCH*') { throw }
            Write-Result 'SOURCE_FAILED' ([string]$ToolSpec.id) $_.Exception.Message
        }
    }
    return $false
}

function Test-IsAdministrator {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = [Security.Principal.WindowsPrincipal]::new($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch { return $false }
}

function Install-Package {
    param($ToolSpec)
    $packagePath = Get-PackagePath $ToolSpec
    $expected = [string]$ToolSpec.package.sha256
    if (-not (Test-PackageHash $packagePath $expected)) {
        Write-Result 'MISSING_PACKAGE' ([string]$ToolSpec.id) "run Download first: $packagePath"
        return $false
    }
    if ($ToolSpec.install.requires_admin -and -not (Test-IsAdministrator)) {
        Write-Result 'ADMIN_REQUIRED' ([string]$ToolSpec.id) 'restart the approved install step in an elevated PowerShell'
        return $false
    }
    $arguments = @($ToolSpec.install.arguments | ForEach-Object { [string]$_ })
    $type = [string]$ToolSpec.install.type
    if ($type -eq 'zip') {
        $target = Join-Path (Join-Path $InstallDir ([string]$ToolSpec.id)) ([string]$ToolSpec.version)
        if (Test-Path -LiteralPath $target) {
            Write-Result 'INSTALL_BLOCKED' ([string]$ToolSpec.id) "target already exists: $target"
            return $false
        }
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        try {
            Expand-Archive -LiteralPath $packagePath -DestinationPath $target
        } catch {
            Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
            throw
        }
    } elseif ($type -eq 'msi') {
        $process = Start-Process -FilePath 'msiexec.exe' -ArgumentList (@('/i', $packagePath) + $arguments) -Wait -PassThru
        if ($process.ExitCode -ne 0) { throw "Installer exited with $($process.ExitCode)" }
    } elseif ($type -eq 'exe') {
        $process = Start-Process -FilePath $packagePath -ArgumentList $arguments -Wait -PassThru
        if ($process.ExitCode -ne 0) { throw "Installer exited with $($process.ExitCode)" }
    } else {
        throw "Unsupported install type: $type"
    }
    Write-Result 'INSTALLED' ([string]$ToolSpec.id) "type=$type"
    return $true
}

$manifest = Read-JsonFile ([IO.Path]::GetFullPath($ManifestPath))
if ($manifest.schema_version -ne 1) { throw "Unsupported toolchain schema_version: $($manifest.schema_version)" }
$selectedTools = @(Get-SelectedTools $manifest)
$localConfig = Read-LocalConfig
$failures = 0

if ($Action -eq 'Plan') {
    foreach ($item in $selectedTools) {
        $path = Find-Executable $item $localConfig
        $probe = Test-Executable $item $path
        if ($probe.Ok) {
            Write-Result 'FOUND' ([string]$item.id) "$($probe.Version) at $path"
        } else {
            $metadataError = Test-PackageMetadata $item
            if ($metadataError) {
                Write-Result 'PENDING_MIRROR' ([string]$item.id) $metadataError
            } else {
                Write-Result 'READY_TO_DOWNLOAD' ([string]$item.id) "file=$($item.package.filename) admin=$($item.install.requires_admin)"
            }
            $failures++
        }
    }
} elseif ($Action -eq 'Download') {
    if (-not $ApproveDownload) {
        Write-Result 'APPROVAL_REQUIRED' 'download' 'rerun with -ApproveDownload after the user approves network/file writes'
        exit 4
    }
    foreach ($item in $selectedTools) {
        $path = Find-Executable $item $localConfig
        if ((Test-Executable $item $path).Ok) {
            Write-Result 'SKIP' ([string]$item.id) "already installed at $path"
        } elseif (-not (Download-Package $item)) { $failures++ }
    }
} elseif ($Action -eq 'Install') {
    if (-not $ApproveInstall) {
        Write-Result 'APPROVAL_REQUIRED' 'install' 'rerun with -ApproveInstall after the user approves installer execution'
        exit 4
    }
    foreach ($item in $selectedTools) {
        $path = Find-Executable $item $localConfig
        if ((Test-Executable $item $path).Ok) {
            Write-Result 'SKIP' ([string]$item.id) "already installed at $path"
            continue
        }
        if (-not (Install-Package $item)) { $failures++; continue }
        $path = Find-Executable $item $localConfig
        $probe = Test-Executable $item $path
        if ($probe.Ok) {
            $localConfig[[string]$item.override_env] = $path
            Write-Result 'PASS' ([string]$item.id) "$($probe.Version) at $path"
        } else {
            Write-Result 'VERIFY_FAILED' ([string]$item.id) $probe.Detail
            $failures++
        }
    }
    Save-LocalConfig $localConfig
} elseif ($Action -eq 'Verify') {
    foreach ($item in $selectedTools) {
        $path = Find-Executable $item $localConfig
        $probe = Test-Executable $item $path
        if ($probe.Ok) {
            Write-Result 'PASS' ([string]$item.id) "$($probe.Version) at $path"
            $localConfig[[string]$item.override_env] = $path
        } else {
            Write-Result 'FAIL' ([string]$item.id) $probe.Detail
            $failures++
        }
    }
    if ($WriteLocalConfig) { Save-LocalConfig $localConfig }
}

if ($failures -gt 0) { exit 2 }
exit 0
