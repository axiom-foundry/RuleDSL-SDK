# Audit Answer Template: Replay Proof v1

- Status: DRAFT
- Date: 2026-02-21

## Problem statement

How do we prove the decision taken on date X can be reproduced?

This template documents a reproducible, evidence-first answer based on replay decision records and strict comparison of equality fields.

## Scope boundary

This template covers:
- Equality proof for two `replay_proof_v1` decision records.
- Strict verifier behavior and machine-readable PASS/FAIL reports.

This template does not cover:
- Persistence/storage guarantees.
- Network delivery or transport trust.
- Distributed consensus semantics.
- Wall-clock trust or timestamp authenticity.

## Required artifacts

- Decision record JSON files (`schema_version = replay_proof_v1`).
- Verifier tool: `Tools/replay_proof/verify_replay_proof.py`.
- PASS report JSON and FAIL report JSON (FAIL report is optional but recommended).
- Embedded fingerprints: `engine_version_string`, `abi_level`, `bytecode_hash`.

## Equality surface

MUST match:
- `engine_version_string`
- `abi_level`
- `bytecode_hash`
- `input_hash` (when present on both records; required in `--strict`)
- `decision_hash` (or `result_hash` fallback)

Informational only:
- `timestamp_utc`
- `notes`
- `error_message`

## Procedure (Windows PowerShell)

PASS example (A vs A), expected exit code `0`:

```powershell
python Tools/replay_proof/verify_replay_proof.py `
  --a <A.json> `
  --b <B_same.json> `
  --out <pass_report.json> `
  --strict
```

FAIL example (A vs B), expected exit code `2`:

```powershell
python Tools/replay_proof/verify_replay_proof.py `
  --a <A.json> `
  --b <B_different.json> `
  --out <fail_report.json> `
  --strict
```

## Interpretation

- PASS (`0`): equality surface matches; replay proof holds for provided artifacts.
- FAIL (`2`): at least one equality field differs; replay proof does not hold for provided artifacts.
- Invalid input/schema (`1`): records are malformed, incompatible, or missing required fields.

## FAQ

- Why strict?
  - `--strict` prevents silent comparison downgrades (for example missing `input_hash`).
- What if `input_hash` is missing?
  - In strict mode verification fails; without strict it may be skipped, which weakens proof quality.
- What if engine version changes?
  - `engine_version_string` mismatch yields FAIL; evidence is not comparable across different engine versions.
- Can I compare across machines?
  - Yes, if both records preserve the required artifacts and equality fields.

## Related links

- RFC-001 System Boundary: `docs/governance/rfc_001_system_boundary_v1.md`
- RFC-001 Test Matrix: `docs/governance/rfc_001_test_matrix_v1.md`
- Replay proof verifier README: `Tools/replay_proof/README.md`
- Replay proof schema v1: `Tools/replay_proof/replay_proof_schema_v1.md`
