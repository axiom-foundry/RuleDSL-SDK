param(
    [Parameter(Mandatory = $true)]
    [string]$EngineBin,
    [Parameter(Mandatory = $true)]
    [string]$CompilerBin,
    [string]$EngineImportLib = "",
    [string]$Out = ""
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

"LICENSE PLACEHOLDER - PROVIDED IN COMMERCIAL DELIVERY" | Set-Content -Path (Join-Path $outRoot "LICENSE") -Encoding utf8
"NOTICE PLACEHOLDER - PROVIDED IN COMMERCIAL DELIVERY" | Set-Content -Path (Join-Path $outRoot "NOTICE") -Encoding utf8

# Final bundle validation guardrails.
foreach ($requiredDir in @($includeOut, $binOut, $docsOut, $examplesOut)) {
    if (-not (Test-Path $requiredDir)) {
        throw "Bundle missing required directory: $requiredDir"
    }
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

$exampleBuildArtifacts = Get-ChildItem -Recurse -Directory $examplesOut | Where-Object { $_.Name -ieq "build" }
if ($exampleBuildArtifacts) {
    $list = ($exampleBuildArtifacts | ForEach-Object { $_.FullName }) -join "; "
    throw "Bundle examples include build directories: $list"
}

Write-Host "Bundle created: $outRoot"
Write-Host "- include/: $(Join-Path $outRoot 'include')"
Write-Host "- bin/: $(Join-Path $outRoot 'bin')"
Write-Host "- docs/: $(Join-Path $outRoot 'docs')"
Write-Host "- examples/: $(Join-Path $outRoot 'examples')"
