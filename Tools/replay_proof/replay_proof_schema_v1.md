# Replay Proof Schema v1

This document defines the minimal decision-record schema used by `verify_replay_proof.py`.

## Decision record format

Top-level JSON object.

Required fields:

- `schema_version` (string): MUST be `"replay_proof_v1"`.
- `engine_version_string` (string): engine/runtime version fingerprint.
- `abi_level` (string or integer): public ABI level fingerprint.
- `bytecode_hash` (string): lowercase SHA-256 hex fingerprint of evaluated bytecode bytes.
- `decision_hash` (string) OR `result_hash` (string): lowercase SHA-256 hex fingerprint of the decision/result payload bytes.

Optional but recommended fields:

- `input_hash` (string): lowercase SHA-256 hex fingerprint of canonical input bytes.
- `input_descriptor` (string): stable descriptor when `input_hash` is not available.

Optional informational fields:

- `error_code` (string or integer)
- `error_message` (string)
- `notes` (string)
- `timestamp_utc` (string)

## Equality rules (replay proof)

The verifier compares equality fields as follows:

MUST match:

- `engine_version_string`
- `abi_level` (normalized to string)
- `bytecode_hash`
- effective result hash (`decision_hash` if present, otherwise `result_hash`)

Conditional equality:

- If both records include `input_hash`, they MUST match.
- If both records include `error_code`, they MUST match.
- In `--strict` mode, `input_hash` MUST be present in both records and MUST match; `error_code` presence mismatch is treated as failure.

Informational-only fields (ignored for equality):

- `input_descriptor`
- `error_message`
- `notes`
- `timestamp_utc`

## Output contract

The verifier emits PASS/FAIL and a machine-readable report with mismatched fields and a deterministic `proof_hash` computed from canonical equality-field concatenation.
