# Evidence Index

## Snapshot metadata

Captured at commit: 589e042c22fe20f4a5541419eadf35091a7e3f01
Captured on: 2026-02-20 (UTC)

## 1) Governance snapshots

- [`governance_snapshot_raw.json`](governance_snapshot_raw.json)
- [`governance_snapshot_post.json`](governance_snapshot_post.json)

These files capture repository ruleset configuration before and after the documented governance update.
Snapshots are captured via GitHub Rulesets API.
Note: list endpoints can omit detailed rule fields; single ruleset fetch by ID is the source of truth.

## 2) Release audit snapshots

- [`release_audit_v1.0.0-rc.1.md`](release_audit_v1.0.0-rc.1.md)

This file captures audit evidence for one release tag: tag name, workflow run id, and downloaded asset hashes.
This is an audit record, not a determinism comparison artifact.

## 3) How to reproduce snapshots (commands)

Rulesets:

```powershell
gh api repos/axiom-foundry/RuleDSL-SDK/rulesets
# pick ruleset id from output

gh api repos/axiom-foundry/RuleDSL-SDK/rulesets/<ID>
gh api repos/axiom-foundry/RuleDSL-SDK/rules/branches/main
```

Release assets and hashes:

```powershell
gh release view v1.0.0-rc.1 --repo axiom-foundry/RuleDSL-SDK --json tagName,publishedAt,assets
gh release download v1.0.0-rc.1 --repo axiom-foundry/RuleDSL-SDK --dir C:\dev\RC\audit\v1.0.0-rc.1 --clobber
Get-ChildItem C:\dev\RC\audit\v1.0.0-rc.1 -File | Sort-Object Name |
  ForEach-Object { "{0}  {1}" -f $_.Name, ((Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()) }
```
