# Release Audit Summary Plan

This document proposes future CI work only.
No CI, script, or tooling implementation is included in this change.

## What

Add a machine-readable release audit artifact:

`audit_summary.json`

Proposed shape:

```json
{
  "tag": "vX.Y.Z",
  "commit": "<full_sha>",
  "run_id": "<github_actions_run_id>",
  "published_at": "<iso8601_or_null>",
  "assets": [
    { "name": "<file>", "sha256": "<hex>", "size": 0 }
  ]
}
```

## Where in CI

Generate the summary after `checksum` and before `publish` in the tag release workflow.

## Determinism rule

- Do not mutate built artifacts.
- Emit `audit_summary.json` as a separate artifact/output.
- Derive values from existing immutable sources (tag, commit, run id, checksum outputs).

## Why

- Provides a single machine-readable audit record.
- Simplifies post-release evidence collection.
- Enables later automated ingestion without changing package contents.

## Non-goal

This document is a future-work note only; no implementation in this commit.
