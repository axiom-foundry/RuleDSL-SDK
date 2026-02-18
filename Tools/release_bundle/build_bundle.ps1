param(
    [Parameter(Mandatory = $true)]
    [string]$EngineBin,
    [Parameter(Mandatory = $true)]
    [string]$CompilerBin,
    [string]$EngineImportLib = "",
    [string]$Out = ""
)

$ErrorActionPreference = "Stop"

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
Copy-Item -Force $CompilerBin (Join-Path $binOut "ruledslc$([System.IO.Path]::GetExtension($CompilerBin))")

if ($EngineImportLib) {
    Copy-Item -Force $EngineImportLib (Join-Path $binOut ([System.IO.Path]::GetFileName($EngineImportLib)))
}

$docFiles = @(
    "docs/bytecode_workflow_v0_9.md",
    "docs/compiler/ruledslc_contract.md",
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

$licensePath = Join-Path $outRoot "LICENSE"
$noticePath = Join-Path $outRoot "NOTICE"
"LICENSE PLACEHOLDER - PROVIDED IN COMMERCIAL DELIVERY" | Set-Content -Path $licensePath -Encoding utf8
"NOTICE PLACEHOLDER - PROVIDED IN COMMERCIAL DELIVERY" | Set-Content -Path $noticePath -Encoding utf8

Write-Host "Bundle created: $outRoot"
Write-Host "- include/: $(Join-Path $outRoot 'include')"
Write-Host "- bin/: $(Join-Path $outRoot 'bin')"
Write-Host "- docs/: $(Join-Path $outRoot 'docs')"
Write-Host "- examples/: $(Join-Path $outRoot 'examples')"
