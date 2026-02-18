param(
    [Parameter(Mandatory = $true)]
    [string]$EngineBin,
    [Parameter(Mandatory = $true)]
    [string]$CompilerBin,
    [string]$EngineImportLib = "",
    [string]$Out = "",
    [ValidateSet("Evaluation", "Commercial")]
    [string]$BundleType = "Evaluation",
    [bool]$EmitManifests = $true
)

$ErrorActionPreference = "Stop"
$onWindows = ($env:OS -eq "Windows_NT")

function Test-DependsOnDebugRuntime {
    param([string]$BinaryPath)

    if (-not $onWindows) {
        return $false
    }

    $pattern = 'MSVCP140D\.dll|VCRUNTIME140D\.dll|VCRUNTIME140_1D\.dll|ucrtbased\.dll'
    $dumpbin = Get-Command dumpbin.exe -ErrorAction SilentlyContinue
    if ($dumpbin) {
        $output = & $dumpbin.Source /dependents $BinaryPath 2>$null
        $text = ($output -join "`n")
        return ($text -match $pattern)
    }

    # Fallback: inspect binary bytes for debug runtime import names.
    $bytes = [System.IO.File]::ReadAllBytes($BinaryPath)
    $ascii = [System.Text.Encoding]::ASCII.GetString($bytes)
    return ($ascii -match $pattern)
}

function Get-RelativePathNormalized {
    param(
        [string]$Root,
        [string]$FullPath
    )

    $rootFull = [System.IO.Path]::GetFullPath($Root)
    $pathFull = [System.IO.Path]::GetFullPath($FullPath)

    if (-not $rootFull.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $rootFull += [System.IO.Path]::DirectorySeparatorChar
    }

    $rootUri = [System.Uri]::new($rootFull)
    $pathUri = [System.Uri]::new($pathFull)
    $relUri = $rootUri.MakeRelativeUri($pathUri)
    $rel = [System.Uri]::UnescapeDataString($relUri.ToString())
    return $rel.Replace('\\', '/')
}

function Get-Sha256Hex {
    param([string]$Path)
    $hash = Get-FileHash -Algorithm SHA256 -Path $Path
    return $hash.Hash.ToLowerInvariant()
}

function Get-SortedOrdinal {
    param([string[]]$Items)

    $list = [System.Collections.Generic.List[string]]::new()
    foreach ($item in $Items) {
        $list.Add([string]$item)
    }
    $list.Sort([System.StringComparer]::Ordinal)
    return @($list)
}

function Get-VersionDefineValue {
    param(
        [string]$HeaderPath,
        [string]$DefineName
    )

    if (-not (Test-Path $HeaderPath)) {
        return "UNKNOWN"
    }

    $pattern = '^\s*#define\s+' + [regex]::Escape($DefineName) + '\s+"([^"]+)"\s*$'
    $line = Get-Content $HeaderPath | Where-Object { $_ -match $pattern } | Select-Object -First 1
    if (-not $line) {
        return "UNKNOWN"
    }

    if ($line -match $pattern) {
        return $Matches[1]
    }
    return "UNKNOWN"
}

function Get-RuledslcVersionInfo {
    param([string]$CompilerPath)

    $output = & $CompilerPath --version 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "ruledslc --version failed with exit code $exitCode"
    }

    $lines = @($output | ForEach-Object { $_.ToString().TrimEnd() } | Where-Object { $_ -ne "" })
    if ($lines.Count -eq 0) {
        throw "ruledslc --version returned empty output"
    }

    $full = $lines -join "`n"
    $first = $lines[0]

    $langVersion = "UNKNOWN"
    $axbcVersion = "UNKNOWN"
    $abiLevel = "UNKNOWN"

    if ($first -match "lang=([^;\)]+)") {
        $langVersion = $Matches[1].Trim()
    }
    if ($first -match "axbc=([^;\)]+)") {
        $axbcVersion = $Matches[1].Trim()
    }
    if ($first -match "abi=([^;\)]+)") {
        $abiLevel = $Matches[1].Trim()
    }

    return [ordered]@{
        full         = $full
        primary_line = $first
        lang_version = $langVersion
        axbc_version = $axbcVersion
        abi_level    = $abiLevel
    }
}

function Get-GitShortHash {
    param([string]$RepoRoot)

    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        return "UNKNOWN"
    }
    $hash = & $git.Source -C $RepoRoot rev-parse --short HEAD 2>$null
    if ($LASTEXITCODE -ne 0) {
        return "UNKNOWN"
    }
    return $hash.Trim()
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $Out) {
    $Out = Join-Path $repoRoot "bundle"
}

$EngineBin = (Resolve-Path $EngineBin).Path
$CompilerBin = (Resolve-Path $CompilerBin).Path
if ($EngineImportLib) {
    $EngineImportLib = (Resolve-Path $EngineImportLib).Path
}

if (-not (Test-Path $EngineBin)) {
    throw "Engine binary not found: $EngineBin"
}
if (-not (Test-Path $CompilerBin)) {
    throw "Compiler binary not found: $CompilerBin"
}
if ($EngineImportLib -and -not (Test-Path $EngineImportLib)) {
    throw "Engine import library not found: $EngineImportLib"
}

$debugEngine = Test-DependsOnDebugRuntime -BinaryPath $EngineBin
if ($debugEngine -eq $true) {
    throw "Engine binary appears to depend on debug runtime; provide a release binary: $EngineBin"
}
$debugCompiler = Test-DependsOnDebugRuntime -BinaryPath $CompilerBin
if ($debugCompiler -eq $true) {
    throw "Compiler binary appears to depend on debug runtime; provide a release binary: $CompilerBin"
}

$outRoot = [System.IO.Path]::GetFullPath($Out)
if (Test-Path $outRoot) {
    Remove-Item -Recurse -Force $outRoot
}

$includeOut = Join-Path $outRoot "include"
$binOut = Join-Path $outRoot "bin"
$docsOut = Join-Path $outRoot "docs"
$examplesOut = Join-Path $outRoot "examples"
$manifestsOut = Join-Path $outRoot "manifests"

New-Item -ItemType Directory -Force -Path $includeOut, $binOut, $docsOut, $examplesOut | Out-Null

Copy-Item -Recurse -Force (Join-Path $repoRoot "include\*") $includeOut
Copy-Item -Force $EngineBin (Join-Path $binOut ([System.IO.Path]::GetFileName($EngineBin)))
$compilerOutName = "ruledslc" + [System.IO.Path]::GetExtension($CompilerBin)
Copy-Item -Force $CompilerBin (Join-Path $binOut $compilerOutName)

if ($EngineImportLib) {
    Copy-Item -Force $EngineImportLib (Join-Path $binOut ([System.IO.Path]::GetFileName($EngineImportLib)))
}

$docFiles = @(
    "docs/bytecode_workflow_v0_9.md",
    "docs/compiler/ruledslc_contract.md",
    "docs/compiler/authenticity_policy.md",
    "docs/compatibility_matrix.md",
    "docs/language/spec_v0_9.md",
    "docs/language/grammar_v0_9.md",
    "docs/language/lexical_core_v0_9.md",
    "docs/language/numeric_model_v0_9.md",
    "docs/language/status_v0_9.md"
)

foreach ($rel in $docFiles) {
    $src = Join-Path $repoRoot $rel
    if (-not (Test-Path $src)) {
        throw "Missing required doc: $src"
    }
    $dst = Join-Path $docsOut ($rel -replace '^docs[/\\]', '')
    $dstDir = Split-Path -Parent $dst
    New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    Copy-Item -Force $src $dst
}

$exampleDirs = @("01_risk_scoring", "02_threshold_gate", "03_temporal_rule")
$exampleFiles = @("rules.rule", "main.c", "README.md", "expected_output.txt")
foreach ($name in $exampleDirs) {
    $src = Join-Path $repoRoot (Join-Path "examples" $name)
    if (-not (Test-Path $src)) {
        throw "Missing required example folder: $src"
    }
    $dstRoot = Join-Path $examplesOut $name
    New-Item -ItemType Directory -Force -Path $dstRoot | Out-Null
    foreach ($file in $exampleFiles) {
        $filePath = Join-Path $src $file
        if (-not (Test-Path $filePath)) {
            throw "Missing required example file: $filePath"
        }
        Copy-Item -Force $filePath (Join-Path $dstRoot $file)
    }
}

if ($BundleType -eq "Commercial") {
    "LICENSE PLACEHOLDER - COMMERCIAL DELIVERY TERMS APPLY" | Set-Content -Path (Join-Path $outRoot "LICENSE") -Encoding utf8
}
else {
    "LICENSE PLACEHOLDER - EVALUATION DELIVERY TERMS APPLY" | Set-Content -Path (Join-Path $outRoot "LICENSE") -Encoding utf8
}
"NOTICE PLACEHOLDER - PROVIDED IN COMMERCIAL DELIVERY" | Set-Content -Path (Join-Path $outRoot "NOTICE") -Encoding utf8

if ($EmitManifests) {
    New-Item -ItemType Directory -Force -Path $manifestsOut | Out-Null

    $ruledslcInfo = Get-RuledslcVersionInfo -CompilerPath $CompilerBin
    $engineVersion = Get-VersionDefineValue -HeaderPath (Join-Path $repoRoot "include/axiom/version.h") -DefineName "AXIOM_VERSION_STRING"
    $bundleScriptVersion = Get-GitShortHash -RepoRoot $repoRoot

    $toolchainLines = @(
        "RULEDSLC_VERSION=$($ruledslcInfo.primary_line)",
        "ENGINE_VERSION=$engineVersion",
        "BUNDLE_SCRIPT_VERSION=$bundleScriptVersion"
    )
    $toolchainPath = Join-Path $manifestsOut "TOOLCHAIN.txt"
    $toolchainLines | Set-Content -Path $toolchainPath -Encoding utf8

    $licenseStatusPath = Join-Path $manifestsOut "LICENSE_STATUS.txt"
    $licenseOutput = & $CompilerBin license --status 2>&1
    $licenseExit = $LASTEXITCODE
    $licenseLines = @($licenseOutput | ForEach-Object { $_.ToString().TrimEnd() } | Where-Object { $_ -ne "" })
    if ($licenseExit -eq 0 -and $licenseLines.Count -gt 0) {
        $licenseLines | Set-Content -Path $licenseStatusPath -Encoding utf8
    }
    else {
        "LICENSE=UNKNOWN" | Set-Content -Path $licenseStatusPath -Encoding utf8
    }

    $currentFiles = @(Get-ChildItem -Path $outRoot -Recurse -File)
    $manifestList = @()
    foreach ($file in $currentFiles) {
        $rel = Get-RelativePathNormalized -Root $outRoot -FullPath $file.FullName
        if ($rel -eq "manifests/HASHES.txt") {
            continue
        }
        if ($rel -eq "manifests/MANIFEST.json") {
            continue
        }
        $manifestList += $rel
    }
    $manifestList += "manifests/MANIFEST.json"
    $manifestList = Get-SortedOrdinal -Items (@($manifestList | Select-Object -Unique))

    $manifestObject = [ordered]@{
        bundle_type      = $BundleType
        created_by       = "Tools/release_bundle/build_bundle.ps1"
        ruledslc_version = $ruledslcInfo.primary_line
        engine_version   = $engineVersion
        lang_version     = $ruledslcInfo.lang_version
        axbc_version     = $ruledslcInfo.axbc_version
        abi_level        = $ruledslcInfo.abi_level
        file_list        = $manifestList
    }
    $manifestPath = Join-Path $manifestsOut "MANIFEST.json"
    $manifestJson = $manifestObject | ConvertTo-Json -Depth 8
    $manifestJson | Set-Content -Path $manifestPath -Encoding utf8

    $hashLines = @()
    $filesForHash = @(Get-ChildItem -Path $outRoot -Recurse -File)
    $pathToFull = @{}
    foreach ($file in $filesForHash) {
        $rel = Get-RelativePathNormalized -Root $outRoot -FullPath $file.FullName
        if ($rel -eq "manifests/HASHES.txt") {
            continue
        }
        $pathToFull[$rel] = $file.FullName
    }

    $sortedHashPaths = Get-SortedOrdinal -Items @($pathToFull.Keys)
    foreach ($rel in $sortedHashPaths) {
        $sha = Get-Sha256Hex -Path $pathToFull[$rel]
        $hashLines += "$sha  $rel"
    }
    $hashesPath = Join-Path $manifestsOut "HASHES.txt"
    $hashLines | Set-Content -Path $hashesPath -Encoding utf8
}

# Final bundle validation guardrails.
foreach ($requiredDir in @($includeOut, $binOut, $docsOut, $examplesOut)) {
    if (-not (Test-Path $requiredDir)) {
        throw "Bundle missing required directory: $requiredDir"
    }
}

if ($EmitManifests -and -not (Test-Path $manifestsOut)) {
    throw "Bundle missing required directory: $manifestsOut"
}

$forbiddenExt = @(".pdb", ".obj", ".ilk", ".idb", ".vcxproj", ".cmake")
$forbiddenFiles = Get-ChildItem -Recurse -File $outRoot | Where-Object { $forbiddenExt -contains $_.Extension.ToLowerInvariant() }
if ($forbiddenFiles) {
    $list = ($forbiddenFiles | ForEach-Object { $_.FullName }) -join "; "
    throw "Bundle contains forbidden build artifacts: $list"
}

$includeNonHeaders = Get-ChildItem -Recurse -File $includeOut | Where-Object { $_.Extension.ToLowerInvariant() -ne ".h" }
if ($includeNonHeaders) {
    $list = ($includeNonHeaders | ForEach-Object { $_.FullName }) -join "; "
    throw "Bundle include/ contains non-header files: $list"
}

$allowedBinExt = @(".exe", ".dll", ".lib", ".so", ".a", ".dylib")
$disallowedBinFiles = Get-ChildItem -Recurse -File $binOut | Where-Object { $allowedBinExt -notcontains $_.Extension.ToLowerInvariant() }
if ($disallowedBinFiles) {
    $list = ($disallowedBinFiles | ForEach-Object { $_.FullName }) -join "; "
    throw "Bundle bin/ contains disallowed files: $list"
}

$exampleBuildArtifacts = Get-ChildItem -Recurse -Directory $examplesOut | Where-Object { $_.Name -ieq "build" }
if ($exampleBuildArtifacts) {
    $list = ($exampleBuildArtifacts | ForEach-Object { $_.FullName }) -join "; "
    throw "Bundle examples include build directories: $list"
}

Write-Host "Bundle created: $outRoot"
Write-Host "- type: $BundleType"
Write-Host "- include/: $(Join-Path $outRoot 'include')"
Write-Host "- bin/: $(Join-Path $outRoot 'bin')"
Write-Host "- docs/: $(Join-Path $outRoot 'docs')"
Write-Host "- examples/: $(Join-Path $outRoot 'examples')"
if ($EmitManifests) {
    Write-Host "- manifests/: $(Join-Path $outRoot 'manifests')"
}