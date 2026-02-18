param(
    [Parameter(Mandatory = $true)]
    [string]$BundleDir
)

$ErrorActionPreference = "Stop"

function Fail {
    param([string]$Message)
    Write-Error $Message
    exit 1
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

$bundleRoot = (Resolve-Path $BundleDir -ErrorAction Stop).Path

$requiredDirs = @("include", "bin", "docs", "examples", "manifests")
foreach ($dir in $requiredDirs) {
    $path = Join-Path $bundleRoot $dir
    if (-not (Test-Path $path -PathType Container)) {
        Fail "Missing required directory: $dir"
    }
}

$requiredFiles = @(
    "manifests/MANIFEST.json",
    "manifests/HASHES.txt",
    "manifests/TOOLCHAIN.txt",
    "manifests/LICENSE_STATUS.txt"
)
foreach ($file in $requiredFiles) {
    $path = Join-Path $bundleRoot $file
    if (-not (Test-Path $path -PathType Leaf)) {
        Fail "Missing required file: $file"
    }
}

$forbiddenExt = @(".pdb", ".obj", ".ilk", ".idb", ".vcxproj", ".cmake")
$forbiddenFiles = @(Get-ChildItem -Path $bundleRoot -Recurse -File | Where-Object { $forbiddenExt -contains $_.Extension.ToLowerInvariant() })
if ($forbiddenFiles.Count -gt 0) {
    $list = ($forbiddenFiles | ForEach-Object { Get-RelativePathNormalized -Root $bundleRoot -FullPath $_.FullName }) -join ", "
    Fail "Forbidden artifacts found: $list"
}

$forbiddenDirs = @(Get-ChildItem -Path $bundleRoot -Recurse -Directory | Where-Object {
    $_.Name -ieq "build" -or $_.Name -ieq "out" -or $_.Name -like "cmake-build*"
})
if ($forbiddenDirs.Count -gt 0) {
    $list = ($forbiddenDirs | ForEach-Object { Get-RelativePathNormalized -Root $bundleRoot -FullPath $_.FullName }) -join ", "
    Fail "Forbidden directories found: $list"
}

$manifestPath = Join-Path $bundleRoot "manifests/MANIFEST.json"
$manifestRaw = Get-Content -Path $manifestPath -Raw
$manifest = $manifestRaw | ConvertFrom-Json
if (-not $manifest) {
    Fail "Unable to parse manifests/MANIFEST.json"
}

$fileList = @($manifest.file_list)
if ($fileList.Count -eq 0) {
    Fail "MANIFEST.json file_list is empty"
}

$seenManifest = @{}
foreach ($item in $fileList) {
    if ($seenManifest.ContainsKey($item)) {
        Fail "MANIFEST.json file_list contains duplicates"
    }
    $seenManifest[$item] = $true
}

$sortedFileList = Get-SortedOrdinal -Items $fileList
if (($fileList -join "`n") -ne ($sortedFileList -join "`n")) {
    Fail "MANIFEST.json file_list is not sorted"
}

foreach ($rel in $fileList) {
    if ($rel -match '^([A-Za-z]:|/)' -or $rel.Contains('\\')) {
        Fail "MANIFEST.json file_list contains non-relative or non-normalized path: $rel"
    }
    $full = Join-Path $bundleRoot $rel
    if (-not (Test-Path $full -PathType Leaf)) {
        Fail "MANIFEST.json references missing file: $rel"
    }
}

$hashesPath = Join-Path $bundleRoot "manifests/HASHES.txt"
$hashLines = @(Get-Content -Path $hashesPath)
if ($hashLines.Count -eq 0) {
    Fail "HASHES.txt is empty"
}

$hashEntries = @()
foreach ($line in $hashLines) {
    if ($line -notmatch '^[0-9a-f]{64}  (.+)$') {
        Fail "Invalid HASHES.txt line format: $line"
    }
    $hashEntries += [pscustomobject]@{
        Hash = $line.Substring(0, 64)
        Path = $Matches[1]
    }
}

$hashPaths = @($hashEntries | ForEach-Object { $_.Path })
$seenHashes = @{}
foreach ($item in $hashPaths) {
    if ($seenHashes.ContainsKey($item)) {
        Fail "HASHES.txt contains duplicate path: $item"
    }
    $seenHashes[$item] = $true
}

$sortedHashPaths = Get-SortedOrdinal -Items $hashPaths
if (($hashPaths -join "`n") -ne ($sortedHashPaths -join "`n")) {
    Fail "HASHES.txt entries are not sorted by path"
}

if ($hashPaths -contains "manifests/HASHES.txt") {
    Fail "HASHES.txt must not include itself"
}

foreach ($entry in $hashEntries) {
    if ($entry.Path -match '^([A-Za-z]:|/)' -or $entry.Path.Contains('\\')) {
        Fail "HASHES.txt contains non-relative or non-normalized path: $($entry.Path)"
    }

    $full = Join-Path $bundleRoot $entry.Path
    if (-not (Test-Path $full -PathType Leaf)) {
        Fail "HASHES.txt references missing file: $($entry.Path)"
    }

    $actual = Get-Sha256Hex -Path $full
    if ($actual -ne $entry.Hash) {
        Fail "HASH mismatch for $($entry.Path): expected $($entry.Hash), got $actual"
    }
}

if (($sortedFileList -join "`n") -ne ($sortedHashPaths -join "`n")) {
    $delta = Compare-Object -ReferenceObject $sortedFileList -DifferenceObject $sortedHashPaths
    $detail = ($delta | ForEach-Object { "$($_.SideIndicator) $($_.InputObject)" }) -join "; "
    Fail "MANIFEST file_list and HASHES paths differ: $detail"
}

Write-Host "Bundle layout audit PASS: $bundleRoot"
Write-Host "Checked files: $($hashEntries.Count)"
exit 0