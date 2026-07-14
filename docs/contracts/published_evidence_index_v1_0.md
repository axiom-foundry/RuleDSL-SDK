# Published Evidence Index (v1.0)

## 1. Purpose

This index distinguishes published evidence from reference example paths used in contract docs.  
Published evidence means a concrete evidence bundle has been produced and retained with verification results.  
Reference example paths are naming examples and do not imply public artifact availability.

## 2. Publication policy

- Evidence bundles are not shipped inside SDK release artifacts.
- When evidence is published, it is delivered as:
  - an evidence bundle directory conforming to `docs/contracts/determinism_evidence_bundle_v1_0.md`
  - optional comparison report(s) for cross-platform claims

## 3. Minimum acceptance for a published claim

- Bundle verification passes (`verify-existing` exit code `0`).
- A comparison report is present when a cross-platform claim is made.
- `environment/tool_versions.json` and `environment/platform_fingerprint.json` are present.

## 4. Current v1.0 status

| Requirement | Status |
| --- | --- |
| DET-001 | **Published 2026-06-21**: linux-x64 + windows-x64 bundles (`verify-existing` rc 0) + cross-platform compare report (`status: pass`, `equal_output: true`). See `reports/determinism_v1_0/2026-06-21/` and `reports/determinism_compare_v1/2026-06-21/DET-001/`. **Latest: 2026-07-11** (v1.0.2 engine; hashes identical to the 2026-06-21/2026-06-23 sets) — see `reports/determinism_compare_v1/2026-07-11/DET-001/`. |
| DET-002 | **Published 2026-06-23**: linux-x64 bundle (`verify-existing` rc 0); single-platform locale/timezone case (envA == envB), so no cross-platform compare report applies. Locale provisioning caveats documented. **Latest: 2026-07-11** (v1.0.2 engine) — see `reports/determinism_v1_0/2026-07-11/linux-x64/ci-linux-det002/`. |
| DET-003 | **Published 2026-06-21**: linux-x64 + windows-x64 bundles (`verify-existing` rc 0) + cross-platform compare report (`status: pass`, `equal_output: true`). See `reports/determinism_compare_v1/2026-06-21/DET-003/`. **Latest: 2026-07-11** (v1.0.2 engine; hashes identical to the 2026-06-21/2026-06-23 sets) — see `reports/determinism_compare_v1/2026-07-11/DET-003/`. |

Multi-host (same-platform, multiple machines): a first committed cross-machine reproduction is **published 2026-07-14** — a fresh Windows-x64 desktop, running the shipped v1.0.2 binaries with the integrity chain verified (bundle SHA -> DLL SHA -> bytecode SHA), reproduced the DET-001 and DET-003 golden outputs byte-for-byte. See `reports/cross_machine_replay_v1/2026-07-14/`. Broader multi-host and independent third-party reproduction remain open.
