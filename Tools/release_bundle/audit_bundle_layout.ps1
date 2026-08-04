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
    return $rel.Replace('\', '/')
}

function Get-Sha256Hex {
    param([string]$Path)
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $Path
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

function Assert-FullLowerCommitSha {
    param(
        [object]$Value,
        [string]$Source
    )

    if (-not ($Value -is [string]) -or -not [System.Text.RegularExpressions.Regex]::IsMatch(
        [string]$Value,
        '^[0-9a-f]{40}$',
        [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
    )) {
        Fail "$Source must be an exact lowercase 40-hex Git commit SHA"
    }
    return [string]$Value
}

function Assert-SafeRelativeBundlePath {
    param(
        [object]$Value,
        [string]$Source
    )

    if (-not ($Value -is [string])) {
        Fail "$Source path must be a string"
    }

    $path = [string]$Value
    if ([string]::IsNullOrEmpty($path)) {
        Fail "$Source contains an empty path"
    }
    if ($path -cne $path.Trim()) {
        Fail "$Source contains a non-normalized path with outer whitespace: $path"
    }
    if ($path.Contains('\')) {
        Fail "$Source contains a backslash path: $path"
    }
    if ($path.StartsWith('/', [System.StringComparison]::Ordinal) -or $path -match '^[A-Za-z]:') {
        Fail "$Source contains an absolute path: $path"
    }
    if ($path.Contains(':')) {
        Fail "$Source contains a non-portable path alias: $path"
    }
    if ($path -match '[\x00-\x1f\x7f]') {
        Fail "$Source contains control characters in a path"
    }

    $segments = $path.Split([char[]]@('/'), [System.StringSplitOptions]::None)
    if ($segments.Count -eq 0 -or $segments -contains '') {
        Fail "$Source contains an empty or repeated path segment: $path"
    }
    foreach ($segment in $segments) {
        if ($segment -eq '.' -or $segment -eq '..') {
            Fail "$Source contains prohibited '.' or '..' segment: $path"
        }
        if ($segment -cne $segment.Trim()) {
            Fail "$Source contains a non-normalized whitespace segment: $path"
        }
    }

    return $path
}

function Get-ContainedBundleFilePath {
    param(
        [string]$BundleRoot,
        [string]$RelativePath,
        [string]$Source
    )

    $rootFull = [System.IO.Path]::GetFullPath($BundleRoot)
    if (-not $rootFull.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $rootFull += [System.IO.Path]::DirectorySeparatorChar
    }
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $BundleRoot $RelativePath))
    $comparison = if ($env:OS -eq "Windows_NT") {
        [System.StringComparison]::OrdinalIgnoreCase
    }
    else {
        [System.StringComparison]::Ordinal
    }
    if (-not $candidate.StartsWith($rootFull, $comparison)) {
        Fail "$Source escapes the bundle root: $RelativePath"
    }
    return $candidate
}

function Get-UniqueToolchainValue {
    param(
        [string[]]$Lines,
        [string]$Name
    )

    $prefix = "$Name="
    $matches = @($Lines | Where-Object { $_.StartsWith($prefix, [System.StringComparison]::Ordinal) })
    if ($matches.Count -ne 1) {
        Fail "TOOLCHAIN.txt must contain exactly one $Name entry"
    }
    return $matches[0].Substring($prefix.Length)
}

$bundleItem = Get-Item -LiteralPath $BundleDir -Force -ErrorAction Stop
if (-not $bundleItem.PSIsContainer) {
    Fail "BundleDir is not a directory: $BundleDir"
}
if (($bundleItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
    Fail "Bundle root must not be a reparse point or symbolic link"
}
$bundleRoot = $bundleItem.FullName

$reparseEntries = @(Get-ChildItem -LiteralPath $bundleRoot -Force -Recurse | Where-Object {
    ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
})
if ($reparseEntries.Count -gt 0) {
    $list = ($reparseEntries | ForEach-Object {
        Get-RelativePathNormalized -Root $bundleRoot -FullPath $_.FullName
    }) -join ", "
    Fail "Bundle contains reparse point or symbolic link: $list"
}

$requiredDirs = @("include", "bin", "docs", "examples", "manifests")
foreach ($dir in $requiredDirs) {
    $path = Join-Path $bundleRoot $dir
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
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
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Fail "Missing required file: $file"
    }
}

$forbiddenExt = @(".pdb", ".obj", ".ilk", ".idb", ".vcxproj", ".cmake")
$forbiddenFiles = @(Get-ChildItem -LiteralPath $bundleRoot -Recurse -File -Force | Where-Object {
    $forbiddenExt -contains $_.Extension.ToLowerInvariant()
})
if ($forbiddenFiles.Count -gt 0) {
    $list = ($forbiddenFiles | ForEach-Object {
        Get-RelativePathNormalized -Root $bundleRoot -FullPath $_.FullName
    }) -join ", "
    Fail "Forbidden artifacts found: $list"
}

$forbiddenDirs = @(Get-ChildItem -LiteralPath $bundleRoot -Recurse -Directory -Force | Where-Object {
    $_.Name -ieq "build" -or $_.Name -ieq "out" -or $_.Name -like "cmake-build*"
})
if ($forbiddenDirs.Count -gt 0) {
    $list = ($forbiddenDirs | ForEach-Object {
        Get-RelativePathNormalized -Root $bundleRoot -FullPath $_.FullName
    }) -join ", "
    Fail "Forbidden directories found: $list"
}

$manifestPath = Join-Path $bundleRoot "manifests/MANIFEST.json"
$manifestRaw = Get-Content -LiteralPath $manifestPath -Raw
$manifest = $manifestRaw | ConvertFrom-Json
if (-not $manifest) {
    Fail "Unable to parse manifests/MANIFEST.json"
}

$engineSourceSha = Assert-FullLowerCommitSha -Value $manifest.engine_source_sha -Source "MANIFEST.json engine_source_sha"
$sdkSourceSha = Assert-FullLowerCommitSha -Value $manifest.sdk_source_sha -Source "MANIFEST.json sdk_source_sha"

$toolchainPath = Join-Path $bundleRoot "manifests/TOOLCHAIN.txt"
$toolchainLines = @(Get-Content -LiteralPath $toolchainPath)
$toolchainEngineSha = Get-UniqueToolchainValue -Lines $toolchainLines -Name "ENGINE_SOURCE_SHA"
$toolchainSdkSha = Get-UniqueToolchainValue -Lines $toolchainLines -Name "SDK_SOURCE_SHA"
Assert-FullLowerCommitSha -Value $toolchainEngineSha -Source "TOOLCHAIN.txt ENGINE_SOURCE_SHA" | Out-Null
Assert-FullLowerCommitSha -Value $toolchainSdkSha -Source "TOOLCHAIN.txt SDK_SOURCE_SHA" | Out-Null
if ($toolchainEngineSha -cne $engineSourceSha) {
    Fail "TOOLCHAIN.txt ENGINE_SOURCE_SHA does not match MANIFEST.json engine_source_sha"
}
if ($toolchainSdkSha -cne $sdkSourceSha) {
    Fail "TOOLCHAIN.txt SDK_SOURCE_SHA does not match MANIFEST.json sdk_source_sha"
}

$fileList = @($manifest.file_list)
if ($fileList.Count -eq 0) {
    Fail "MANIFEST.json file_list is empty"
}

$seenManifest = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
$seenManifestPortable = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($item in $fileList) {
    if (-not ($item -is [string])) {
        Fail "MANIFEST.json file_list path must be a string"
    }
    if (-not $seenManifest.Add([string]$item)) {
        Fail "MANIFEST.json file_list contains duplicate path: $item"
    }
    if (-not $seenManifestPortable.Add([string]$item)) {
        Fail "MANIFEST.json file_list contains case-colliding path alias: $item"
    }
}

$sortedFileList = Get-SortedOrdinal -Items $fileList
if (($fileList -join "`n") -cne ($sortedFileList -join "`n")) {
    Fail "MANIFEST.json file_list is not sorted"
}

foreach ($item in $fileList) {
    $rel = Assert-SafeRelativeBundlePath -Value $item -Source "MANIFEST.json file_list"
    $full = Get-ContainedBundleFilePath -BundleRoot $bundleRoot -RelativePath $rel -Source "MANIFEST.json file_list"
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
        Fail "MANIFEST.json references missing file: $rel"
    }
}

$hashesPath = Join-Path $bundleRoot "manifests/HASHES.txt"
$hashLines = @(Get-Content -LiteralPath $hashesPath)
if ($hashLines.Count -eq 0) {
    Fail "HASHES.txt is empty"
}

$hashEntries = @()
foreach ($line in $hashLines) {
    $match = [System.Text.RegularExpressions.Regex]::Match(
        $line,
        '^([0-9a-f]{64})  (.+)$',
        [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
    )
    if (-not $match.Success) {
        Fail "Invalid HASHES.txt line format: $line"
    }
    $hashEntries += [pscustomobject]@{
        Hash = $match.Groups[1].Value
        Path = $match.Groups[2].Value
    }
}

$hashPaths = @($hashEntries | ForEach-Object { $_.Path })
$seenHashes = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
$seenHashesPortable = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($item in $hashPaths) {
    if (-not $seenHashes.Add($item)) {
        Fail "HASHES.txt contains duplicate path: $item"
    }
    if (-not $seenHashesPortable.Add($item)) {
        Fail "HASHES.txt contains case-colliding path alias: $item"
    }
}

$sortedHashPaths = Get-SortedOrdinal -Items $hashPaths
if (($hashPaths -join "`n") -cne ($sortedHashPaths -join "`n")) {
    Fail "HASHES.txt entries are not sorted by path"
}

if ($hashPaths -contains "manifests/HASHES.txt") {
    Fail "HASHES.txt must not include itself"
}

foreach ($entry in $hashEntries) {
    $rel = Assert-SafeRelativeBundlePath -Value $entry.Path -Source "HASHES.txt"
    $full = Get-ContainedBundleFilePath -BundleRoot $bundleRoot -RelativePath $rel -Source "HASHES.txt"
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
        Fail "HASHES.txt references missing file: $rel"
    }

    $actual = Get-Sha256Hex -Path $full
    if ($actual -cne $entry.Hash) {
        Fail "HASH mismatch for $rel`: expected $($entry.Hash), got $actual"
    }
}

if (($sortedFileList -join "`n") -cne ($sortedHashPaths -join "`n")) {
    $delta = Compare-Object -ReferenceObject $sortedFileList -DifferenceObject $sortedHashPaths -CaseSensitive
    $detail = ($delta | ForEach-Object { "$($_.SideIndicator) $($_.InputObject)" }) -join "; "
    Fail "MANIFEST file_list and HASHES paths differ: $detail"
}

$actualPaths = @(Get-ChildItem -LiteralPath $bundleRoot -Recurse -File -Force | ForEach-Object {
    Get-RelativePathNormalized -Root $bundleRoot -FullPath $_.FullName
} | Where-Object { $_ -cne "manifests/HASHES.txt" })
$actualPaths = Get-SortedOrdinal -Items $actualPaths

if (($sortedFileList -join "`n") -cne ($actualPaths -join "`n")) {
    $delta = Compare-Object -ReferenceObject $sortedFileList -DifferenceObject $actualPaths -CaseSensitive
    $detail = ($delta | ForEach-Object { "$($_.SideIndicator) $($_.InputObject)" }) -join "; "
    Fail "Bundle file inventory differs from MANIFEST/HASHES; unlisted or unhashed file, or listed file absent: $detail"
}

Write-Host "Bundle layout audit PASS: $bundleRoot"
Write-Host "Checked files: $($hashEntries.Count)"
Write-Host "Engine source SHA: $engineSourceSha"
Write-Host "SDK source SHA: $sdkSourceSha"
exit 0
