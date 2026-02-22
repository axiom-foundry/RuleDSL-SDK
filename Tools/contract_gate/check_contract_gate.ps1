Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($env:GITHUB_EVENT_NAME -ne 'pull_request' -and $env:GITHUB_EVENT_NAME -ne 'pull_request_target') {
    Write-Host 'Not a pull_request event; contract gate skipped.'
    exit 0
}

if ([string]::IsNullOrWhiteSpace($env:GITHUB_EVENT_PATH) -or -not (Test-Path $env:GITHUB_EVENT_PATH)) {
    throw 'GITHUB_EVENT_PATH is missing or invalid.'
}

$event = Get-Content -Raw -Path $env:GITHUB_EVENT_PATH | ConvertFrom-Json
if (-not $event.pull_request) {
    throw 'pull_request payload is missing in event JSON.'
}

$baseSha = [string]$event.pull_request.base.sha
$headSha = [string]$event.pull_request.head.sha
$prBody = [string]$event.pull_request.body

if ([string]::IsNullOrWhiteSpace($baseSha) -or [string]::IsNullOrWhiteSpace($headSha)) {
    throw 'Unable to resolve base/head SHAs for PR diff.'
}

$changedFiles = @(git diff --name-only $baseSha $headSha)
if ($LASTEXITCODE -ne 0) {
    throw 'git diff failed while resolving changed files.'
}

$frozenPatterns = @(
    '^include/',
    '^docs/architecture/',
    '^docs/language/',
    '^docs/governance/',
    '^docs/bytecode_workflow_'
)

$touchedFrozen = @()
foreach ($file in $changedFiles) {
    if ([string]::IsNullOrWhiteSpace($file)) {
        continue
    }

    foreach ($pattern in $frozenPatterns) {
        if ($file -match $pattern) {
            $touchedFrozen += $file
            break
        }
    }
}

$touchedFrozen = @($touchedFrozen | Sort-Object -Unique)
if ($touchedFrozen.Count -eq 0) {
    Write-Host 'No frozen surface changes detected. Contract gate passed.'
    exit 0
}

Write-Host 'Frozen surface changes detected:'
$touchedFrozen | ForEach-Object { Write-Host "- $_" }

if ($prBody -match '(?m)^\s*Contract change:\s*YES\s*$') {
    Write-Host 'Contract gate passed: PR body declares "Contract change: YES".'
    exit 0
}

Write-Error 'Contract gate failed: frozen surfaces changed but PR body is missing exact line "Contract change: YES".'
exit 1
