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

Optional equality fields (all required by `--strict`):

- `input_hash` (string): lowercase SHA-256 hex fingerprint of canonical input bytes.
- `options_hash` (string): lowercase SHA-256 hex fingerprint of canonical explicit
  evaluation-option bytes.
- `validation_outcome` (string): non-empty producer/binding validation outcome.
- `validation_code` (integer): stable producer/binding validation code.

Optional informational fields:

- `input_descriptor` (string): stable descriptor when `input_hash` is not available.
- `error_code` (string or integer)
- `error_message` (string)
- `notes` (string)
- `timestamp_utc` (string)

The shipped producers serialize input and option objects as UTF-8 JSON with
sorted keys and no insignificant whitespace before hashing. When no explicit
evaluation options are supplied, they hash the canonical empty object, the
bytes `{}`, whose SHA-256 is
`44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`.

`validation_outcome` and `validation_code` describe validation performed by
the producer/binding. They are not fields emitted by the engine decision. The
shipped successful-evaluation producers emit `"OK"` and `0`; they emit a record
only after validation and evaluation succeed.

## Equality rules (replay proof)

The verifier compares equality fields as follows:

MUST match:

- `engine_version_string`
- `abi_level` (normalized to string)
- `bytecode_hash`
- effective result hash (`decision_hash` if present, otherwise `result_hash`)

Conditional equality:

- If both records include `input_hash`, `options_hash`, `validation_outcome`,
  or `validation_code`, the corresponding values MUST match.
- If both records include `error_code`, they MUST match.
- In `--strict` mode, `input_hash`, `options_hash`, `validation_outcome`, and
  `validation_code` MUST be present in both records and MUST match;
  `error_code` presence mismatch is treated as failure.

Informational-only fields (ignored for equality):

- `input_descriptor`
- `error_message`
- `notes`
- `timestamp_utc`

## Output contract

The verifier emits PASS/FAIL and a machine-readable report with mismatched fields and a deterministic `proof_hash` computed from canonical equality-field concatenation.
