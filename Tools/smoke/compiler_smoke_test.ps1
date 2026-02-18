param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$CompilerBin = "ruledslc",
    [Parameter(Mandatory = $true)]
    [string]$EngineLibDir,
    [string]$IncludeDir = "",
    [string]$ReportDir = ""
)

$ErrorActionPreference = "Stop"

function Resolve-Tool {
    param([string]$Candidate)

    if ([System.IO.Path]::IsPathRooted($Candidate)) {
        if (Test-Path $Candidate) {
            return (Resolve-Path $Candidate).Path
        }
        throw "Compiler binary not found: $Candidate"
    }

    $cmd = Get-Command $Candidate -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    throw "Compiler binary '$Candidate' not found in PATH."
}

$RepoRoot = (Resolve-Path $RepoRoot).Path
$EngineLibDir = (Resolve-Path $EngineLibDir).Path
if (-not $IncludeDir) {
    $IncludeDir = Join-Path $RepoRoot "include"
}
if (-not $ReportDir) {
    $ReportDir = Join-Path $RepoRoot "reports"
}
if (-not (Test-Path $IncludeDir)) {
    throw "Missing include dir: $IncludeDir"
}

$CompilerExe = Resolve-Tool -Candidate $CompilerBin
$engineImport = Join-Path $EngineLibDir "ruledsl_capi.lib"
$engineDll = Join-Path $EngineLibDir "ruledsl_capi.dll"
if (-not (Test-Path $engineImport)) {
    throw "Missing engine import library: $engineImport"
}
if (-not (Test-Path $engineDll)) {
    throw "Missing engine runtime DLL: $engineDll"
}

$cl = Get-Command cl.exe -ErrorAction SilentlyContinue
$gcc = Get-Command gcc -ErrorAction SilentlyContinue
$vsDevCmd = "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"
if ((-not $cl) -and (Test-Path $vsDevCmd)) {
    $cl = [pscustomobject]@{ Source = "cl.exe"; UseVsDevCmd = $true }
}
if (-not $cl -and -not $gcc) {
    throw "No C compiler found (cl.exe/gcc) and VsDevCmd was not available."
}

New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$workRoot = Join-Path $ReportDir "compiler_smoke_work"
if (Test-Path $workRoot) {
    Remove-Item -Recurse -Force $workRoot
}
New-Item -ItemType Directory -Force -Path $workRoot | Out-Null

$examples = @("01_risk_scoring", "02_threshold_gate", "03_temporal_rule")
$results = @()
$failed = $false

foreach ($name in $examples) {
    $exampleRoot = Join-Path $RepoRoot (Join-Path "examples" $name)
    $rulePath = Join-Path $exampleRoot "rules.rule"
    $sourcePath = Join-Path $exampleRoot "main.c"
    $expectedPath = Join-Path $exampleRoot "expected_output.txt"
    $exampleWork = Join-Path $workRoot $name
    $axbc1 = Join-Path $exampleWork "rules_1.axbc"
    $axbc2 = Join-Path $exampleWork "rules_2.axbc"
    $manifest1 = Join-Path $exampleWork "compile_1.json"
    $manifest2 = Join-Path $exampleWork "compile_2.json"
    $exePath = Join-Path $exampleWork ("eval_" + $name + ".exe")

    New-Item -ItemType Directory -Force -Path $exampleWork | Out-Null

    $row = [ordered]@{
        example = $name
        compile_first_exit = 0
        compile_second_exit = 0
        deterministic_hash_match = $false
        run_exit = 0
        output_match = $false
        status = "PASS"
        detail = ""
    }

    try {
        foreach ($required in @($rulePath, $sourcePath, $expectedPath)) {
            if (-not (Test-Path $required)) {
                throw "Missing example file: $required"
            }
        }

        & $CompilerExe compile $rulePath -o $axbc1 --lang 0.9 --target axbc3 --emit-manifest $manifest1
        $row.compile_first_exit = $LASTEXITCODE
        if ($row.compile_first_exit -ne 0) {
            throw "first compile failed with exit code $($row.compile_first_exit)"
        }

        & $CompilerExe compile $rulePath -o $axbc2 --lang 0.9 --target axbc3 --emit-manifest $manifest2
        $row.compile_second_exit = $LASTEXITCODE
        if ($row.compile_second_exit -ne 0) {
            throw "second compile failed with exit code $($row.compile_second_exit)"
        }

        $h1 = (Get-FileHash $axbc1 -Algorithm SHA256).Hash.ToLowerInvariant()
        $h2 = (Get-FileHash $axbc2 -Algorithm SHA256).Hash.ToLowerInvariant()
        $row.deterministic_hash_match = ($h1 -eq $h2)
        if (-not $row.deterministic_hash_match) {
            throw "determinism hash mismatch ($h1 vs $h2)"
        }

        if ($cl) {
            $clArgs = @(
                "/nologo",
                "/W4",
                "/I", $IncludeDir,
                "/Fo$exampleWork\\",
                $sourcePath,
                "/link",
                "/LIBPATH:$EngineLibDir",
                "ruledsl_capi.lib",
                "/OUT:$exePath"
            )

            if ($cl.PSObject.Properties.Name -contains "UseVsDevCmd") {
                $escaped = ($clArgs | ForEach-Object {
                    if ($_ -match '\\s') { '"' + $_ + '"' } else { $_ }
                }) -join ' '
                $cmdLine = '"' + $vsDevCmd + '" -no_logo -arch=x64 >nul && cl.exe ' + $escaped
                & cmd.exe /d /s /c $cmdLine | Out-Host
            }
            else {
                & $cl.Source @clArgs | Out-Host
            }

            if ($LASTEXITCODE -ne 0) {
                throw "cl compile/link failed with exit code $LASTEXITCODE"
            }
        }
        else {
            $gccArgs = @(
                "-std=c99",
                "-Wall",
                "-Wextra",
                "-I", $IncludeDir,
                $sourcePath,
                "-L", $EngineLibDir,
                "-lruledsl_capi",
                "-o", $exePath
            )
            & $gcc.Source @gccArgs | Out-Host
            if ($LASTEXITCODE -ne 0) {
                throw "gcc compile/link failed with exit code $LASTEXITCODE"
            }
        }

        Copy-Item -Force $engineDll (Join-Path $exampleWork "ruledsl_capi.dll")
        $runOutput = & $exePath $axbc1 2>&1
        $row.run_exit = $LASTEXITCODE
        if ($row.run_exit -ne 0) {
            throw "example run failed with exit code $($row.run_exit): $runOutput"
        }

        $expected = (Get-Content $expectedPath -Raw).Trim()
        $actual = ($runOutput -join "`n").Trim()
        $row.output_match = ($expected -eq $actual)
        if (-not $row.output_match) {
            throw "output mismatch. expected=`"$expected`" actual=`"$actual`""
        }
    }
    catch {
        $failed = $true
        $row.status = "FAIL"
        $row.detail = $_.Exception.Message
    }

    $results += [pscustomobject]$row
}

$jsonPath = Join-Path $ReportDir "compiler_smoke_report.json"
$mdPath = Join-Path $ReportDir "compiler_smoke_report.md"

$summary = [ordered]@{
    status = if ($failed) { "FAIL" } else { "PASS" }
    compiler = $CompilerExe
    engine_lib_dir = $EngineLibDir
    work_dir = $workRoot
    results = $results
}

($summary | ConvertTo-Json -Depth 6) | Set-Content -Path $jsonPath -Encoding utf8

$lines = @()
$lines += "# Compiler Smoke Report"
$lines += ""
$lines += "- Status: **$($summary.status)**"
$lines += "- Compiler: $CompilerExe"
$lines += "- Engine lib dir: $EngineLibDir"
$lines += "- Work dir: $workRoot"
$lines += ""
$lines += "| Example | Deterministic Hash | Output Match | Status | Detail |"
$lines += "| --- | --- | --- | --- | --- |"
foreach ($row in $results) {
    $lines += "| $($row.example) | $($row.deterministic_hash_match) | $($row.output_match) | $($row.status) | $($row.detail) |"
}
$lines -join "`n" | Set-Content -Path $mdPath -Encoding utf8

Write-Host "Report: $mdPath"
Write-Host "Summary: $jsonPath"
if ($failed) {
    foreach ($row in $results | Where-Object { $_.status -eq "FAIL" }) {
        Write-Error ("Smoke failure in {0}: {1}" -f $row.example, $row.detail)
    }
    exit 1
}
exit 0
