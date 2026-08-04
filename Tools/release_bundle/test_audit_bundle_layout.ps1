$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$auditPath = Join-Path $PSScriptRoot "audit_bundle_layout.ps1"
$fixturePath = Join-Path $PSScriptRoot "fixtures/min_bundle"
$powerShellHost = (Get-Process -Id $PID).Path
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ruledsl-bundle-audit-tests-" + [guid]::NewGuid().ToString("N"))

function Copy-Fixture {
    param([string]$Destination)

    New-Item -ItemType Directory -Path $Destination | Out-Null
    Get-ChildItem -LiteralPath $fixturePath -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
    }
}

function Set-ManifestPath {
    param(
        [string]$Bundle,
        [string]$OldPath,
        [string]$NewPath
    )

    $path = Join-Path $Bundle "manifests/MANIFEST.json"
    $manifest = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    $matches = @()
    for ($index = 0; $index -lt $manifest.file_list.Count; $index++) {
        if ($manifest.file_list[$index] -ceq $OldPath) {
            $matches += $index
        }
    }
    if ($matches.Count -ne 1) {
        throw "fixture mutation expected one '$OldPath' path, found $($matches.Count)"
    }
    $manifest.file_list[$matches[0]] = $NewPath
    $json = $manifest | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($path, ($json + "`n"), $utf8NoBom)
}

function Set-HashesPath {
    param(
        [string]$Bundle,
        [string]$OldPath,
        [string]$NewPath
    )

    $path = Join-Path $Bundle "manifests/HASHES.txt"
    $lines = @([System.IO.File]::ReadAllLines($path))
    $matches = @()
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index].EndsWith("  $OldPath", [System.StringComparison]::Ordinal)) {
            $matches += $index
        }
    }
    if ($matches.Count -ne 1) {
        throw "fixture mutation expected one HASHES '$OldPath' path, found $($matches.Count)"
    }
    $hash = $lines[$matches[0]].Substring(0, 64)
    $lines[$matches[0]] = "$hash  $NewPath"
    [System.IO.File]::WriteAllText($path, (($lines -join "`n") + "`n"), $utf8NoBom)
}

function ConvertTo-QuotedProcessArgument {
    param(
        [string]$Value,
        [string]$Name
    )

    if ($null -eq $Value -or $Value.IndexOf([char]0) -ge 0 -or
        $Value.Contains('"') -or $Value.Contains("`r") -or $Value.Contains("`n")) {
        throw "$Name contains characters that cannot be passed safely to the child process"
    }
    return '"' + $Value + '"'
}

function Invoke-AuditProcess {
    param([string]$Bundle)

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $powerShellHost
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.Arguments = @(
        "-NoProfile",
        "-NonInteractive",
        "-File",
        (ConvertTo-QuotedProcessArgument -Value $auditPath -Name "audit script path"),
        "-BundleDir",
        (ConvertTo-QuotedProcessArgument -Value $Bundle -Name "bundle path")
    ) -join " "

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) {
            throw "failed to start audit child process"
        }

        # Drain both redirected streams asynchronously before waiting. Reading
        # either one synchronously first can deadlock when the other pipe fills.
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        $exitCode = $process.ExitCode
    }
    finally {
        $process.Dispose()
    }

    if ($stdout.Length -gt 0 -and $stderr.Length -gt 0 -and
        -not $stdout.EndsWith("`n", [System.StringComparison]::Ordinal)) {
        $output = $stdout + "`n" + $stderr
    }
    else {
        $output = $stdout + $stderr
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $output
        StdOut = $stdout
        StdErr = $stderr
    }
}

function ConvertTo-DiagnosticMatchText {
    param([AllowEmptyString()][string]$Text)

    if ($null -eq $Text) {
        return ""
    }

    # Preserve raw child output for diagnostics. Normalize only assertion text:
    # remove OSC/CSI terminal controls, discard non-whitespace C0 controls, and
    # remove PowerShell 7 rich-error gutters, then join wrapped word boundaries.
    $escape = [regex]::Escape([string][char]27)
    $withoutOsc = [regex]::Replace($Text, ($escape + '\][\s\S]*?(?:\x07|' + $escape + '\\)'), "")
    $withoutCsi = [regex]::Replace($withoutOsc, ($escape + '\[[0-?]*[ -/]*[@-~]'), "")
    $withoutControls = [regex]::Replace($withoutCsi, '[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', "")
    $withoutGutters = [regex]::Replace($withoutControls, '(?m)^[ \t]*(?:\d+[ \t]+)?\|[ \t]?', "")
    return [regex]::Replace($withoutGutters, '\s+', ' ').Trim()
}

function Invoke-AuditCase {
    param(
        [string]$Name,
        [scriptblock]$Mutate,
        [bool]$ShouldPass,
        [string]$ExpectedFragment
    )

    $caseRoot = Join-Path $testRoot $Name
    Copy-Fixture -Destination $caseRoot
    if ($Mutate) {
        & $Mutate $caseRoot
    }

    $result = Invoke-AuditProcess -Bundle $caseRoot
    if ($ShouldPass) {
        if ($result.ExitCode -ne 0) {
            throw "$Name expected exit 0, got $($result.ExitCode): $($result.Output)"
        }
    }
    elseif ($result.ExitCode -eq 0) {
        throw "$Name expected nonzero exit, but audit passed"
    }

    $matchOutput = ConvertTo-DiagnosticMatchText -Text $result.Output
    $matchExpected = ConvertTo-DiagnosticMatchText -Text $ExpectedFragment
    if ($matchOutput.IndexOf($matchExpected, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "$Name output did not contain '$ExpectedFragment': $($result.Output)"
    }
    Write-Host "PASS $Name (exit=$($result.ExitCode), fragment='$ExpectedFragment')"
}

$escapeProbe = [string][char]27
$diagnosticProbe = $escapeProbe + ']8;;https://example.invalid' + $escapeProbe + '\' + 'must be an exact' + "`r`n" + $escapeProbe + '[31;1m' + 'lowercase' + $escapeProbe + '[0m' + "`t" + '40-hex Git' + [string]([char]0) + "`n     | " + $escapeProbe + '[36;1m' + 'commit SHA' + $escapeProbe + '[0m' + $escapeProbe + ']8;;' + $escapeProbe + '\'
$normalizedProbe = ConvertTo-DiagnosticMatchText -Text $diagnosticProbe
if ($normalizedProbe -cne 'must be an exact lowercase 40-hex Git commit SHA') {
    throw "diagnostic normalization self-test failed: $normalizedProbe"
}

New-Item -ItemType Directory -Path $testRoot | Out-Null
try {
    Invoke-AuditCase -Name "valid path with spaces" -ShouldPass $true -ExpectedFragment "Bundle layout audit PASS" -Mutate {}

    Invoke-AuditCase -Name "uppercase-source-sha" -ShouldPass $false -ExpectedFragment "must be an exact lowercase 40-hex Git commit SHA" -Mutate {
        param($bundle)
        $path = Join-Path $bundle "manifests/MANIFEST.json"
        $manifest = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        $manifest.engine_source_sha = $manifest.engine_source_sha.ToUpperInvariant()
        $json = $manifest | ConvertTo-Json -Depth 8
        [System.IO.File]::WriteAllText($path, ($json + "`n"), $utf8NoBom)
    }

    Invoke-AuditCase -Name "toolchain-source-mismatch" -ShouldPass $false -ExpectedFragment "does not match MANIFEST.json engine_source_sha" -Mutate {
        param($bundle)
        $path = Join-Path $bundle "manifests/TOOLCHAIN.txt"
        $text = [System.IO.File]::ReadAllText($path)
        $old = "ENGINE_SOURCE_SHA=0e52050c64620619d6f52317fb281a2b9e6534d3"
        if (([regex]::Matches($text, [regex]::Escape($old))).Count -ne 1) {
            throw "fixture toolchain engine SHA not found exactly once"
        }
        [System.IO.File]::WriteAllText(
            $path,
            $text.Replace($old, ("ENGINE_SOURCE_SHA=" + ("1" * 40))),
            $utf8NoBom
        )
    }

    Invoke-AuditCase -Name "parent-segment" -ShouldPass $false -ExpectedFragment "prohibited '.' or '..' segment" -Mutate {
        param($bundle)
        Set-ManifestPath -Bundle $bundle -OldPath "LICENSE" -NewPath "../LICENSE"
    }

    Invoke-AuditCase -Name "dot-segment" -ShouldPass $false -ExpectedFragment "prohibited '.' or '..' segment" -Mutate {
        param($bundle)
        Set-ManifestPath -Bundle $bundle -OldPath "docs/README.md" -NewPath "docs/./README.md"
    }

    Invoke-AuditCase -Name "hash-dot-segment" -ShouldPass $false -ExpectedFragment "prohibited '.' or '..' segment" -Mutate {
        param($bundle)
        Set-HashesPath -Bundle $bundle -OldPath "docs/README.md" -NewPath "docs/./README.md"
    }

    Invoke-AuditCase -Name "unlisted-extra" -ShouldPass $false -ExpectedFragment "unlisted or unhashed file" -Mutate {
        param($bundle)
        [System.IO.File]::WriteAllText((Join-Path $bundle "unlisted.txt"), "extra`n", $utf8NoBom)
    }

    Invoke-AuditCase -Name "missing-file" -ShouldPass $false -ExpectedFragment "MANIFEST.json references missing file: NOTICE" -Mutate {
        param($bundle)
        Remove-Item -LiteralPath (Join-Path $bundle "NOTICE") -Force
    }

    Invoke-AuditCase -Name "hash-mismatch" -ShouldPass $false -ExpectedFragment "HASH mismatch for NOTICE" -Mutate {
        param($bundle)
        [System.IO.File]::WriteAllText((Join-Path $bundle "NOTICE"), "tampered`n", $utf8NoBom)
    }
}
finally {
    $resolvedTestRoot = [System.IO.Path]::GetFullPath($testRoot)
    $resolvedTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $prefix = $resolvedTempRoot.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    $leaf = [System.IO.Path]::GetFileName($resolvedTestRoot)
    if (-not $resolvedTestRoot.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not $leaf.StartsWith("ruledsl-bundle-audit-tests-", [System.StringComparison]::Ordinal)) {
        throw "refusing unsafe test cleanup path: $resolvedTestRoot"
    }
    Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Bundle audit contract tests PASS"
