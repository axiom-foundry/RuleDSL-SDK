# Cross-Platform Determinism Smoke v1

- Status: DRAFT
- Date: 2026-02-21

## Purpose

Define a minimal, repeatable smoke procedure to validate that replay-proof records from Windows x64 and Linux x64 remain equal on the required determinism surface.

## Required equality surface

The following fields MUST match for a PASS claim:
- `engine_version_string`
- `abi_level`
- `bytecode_hash`
- `input_hash`
- `decision_hash` (or `result_hash` when decision hash is not emitted)

Comparison SHALL be executed with `--strict` mode.

## Procedure

1. Build and run the producer on Windows x64 and emit a decision record (`win_record.json`).
2. Build and run the producer on Linux x64 and emit a decision record (`linux_record.json`).
3. Run replay verification:

```powershell
python Tools/replay_proof/verify_replay_proof.py `
  --a <win_record.json> `
  --b <linux_record.json> `
  --out <cross_platform_report.json> `
  --strict
```

4. Exit code interpretation:
- `0`: smoke PASS
- `2`: deterministic surface mismatch
- `1`: malformed or incompatible evidence record

## Expected failure modes

- Engine or ABI mismatch (`engine_version_string`, `abi_level`).
- Bytecode mismatch (`bytecode_hash`).
- Canonical input mismatch (`input_hash`).
- Decision/result mismatch (`decision_hash` or `result_hash`).
- Missing required fields in strict mode.

## Artifact retention policy

For each smoke run, retain at minimum:
- `win_record.json`
- `linux_record.json`
- `cross_platform_report.json`
- run metadata note (commit IDs, command lines, expected/observed exit code)

Artifacts SHOULD be retained long enough to support release or audit review and MUST remain immutable once referenced by an audit note.
