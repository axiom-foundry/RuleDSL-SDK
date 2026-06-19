# Replay Contract (JSON replay-proof)

Determinism is re-verified by re-running the normal `ax_eval_bytecode` call (declared in
`include/axiom/ruledsl_c.h`) on caller-retained bytecode and input fields, then comparing the
resulting decision records with the offline verifier `Tools/replay_proof/verify_replay_proof.py`.
The determinism evidence is a JSON decision record defined by the `replay_proof_v1` schema
(`Tools/replay_proof/replay_proof_schema_v1.md`). There is no in-process record/replay buffer and
no binary replay blob.

## Decision record (replay_proof_v1)

Replay evidence is a top-level JSON object. Required fields (per
`Tools/replay_proof/replay_proof_schema_v1.md`):

- `schema_version` (string): MUST be `"replay_proof_v1"`.
- `engine_version_string` (string): engine/runtime version fingerprint.
- `abi_level` (string or integer): public ABI level fingerprint.
- `bytecode_hash` (string): lowercase SHA-256 hex of the evaluated bytecode bytes.
- `decision_hash` OR `result_hash` (string): lowercase SHA-256 hex of the decision/result payload.

Optional fields: `input_hash` and `input_descriptor`, plus the informational `error_code`,
`error_message`, `notes`, and `timestamp_utc`.

## Equality rules (replay proof)

The verifier (`verify_replay_proof.py`) treats two decision records as a matching replay proof
when all of the following hold:

- `engine_version_string`, `abi_level` (normalized to string), `bytecode_hash`, and the effective
  result hash (`decision_hash` if present, else `result_hash`) MUST match.
- If both records include `input_hash`, they MUST match; likewise for `error_code`.
- In `--strict` mode, `input_hash` MUST be present in both records and match, and an `error_code`
  presence mismatch is treated as failure.

`input_descriptor`, `error_message`, `notes`, and `timestamp_utc` are informational and ignored for
equality. The verifier emits PASS/FAIL with the mismatched fields and a deterministic `proof_hash`
computed from the canonical equality-field concatenation.

## Versioning and Extension Policy

- `schema_version` identifies the record schema and MUST be exactly `"replay_proof_v1"`;
  `verify_replay_proof.py` rejects any other value.
- Evolution within v1.x is additive-only and MUST NOT change the meaning of existing fields.
- Breaking changes require a new major schema version string.
- New fields MUST preserve the deterministic, locale-independent canonicalization used for equality.

## Guarantees

- Evaluation runs in-process via `ax_eval_bytecode`; the library introduces no file I/O, network
  I/O, or database dependency.
- Replay-proof verification is performed offline by `verify_replay_proof.py`, which validates each
  JSON record's required fields and SHA-256 hex hashes.
- For identical bytecode and identical inputs, re-running `ax_eval_bytecode` yields identical
  decision outputs, which the verifier confirms as matching records.

## Ownership Rules

- The caller owns `AXBytecode` and must release it with `ax_bytecode_free`.
- The caller owns `AXDecision` and must release SDK-owned strings with `ax_decision_reset`
  (alias `ax_decision_free`) before reuse or discard.
- The caller owns and retains the bytecode and input fields needed to re-run `ax_eval_bytecode`
  for replay.
- Decision records and verifier reports are plain JSON files owned and managed by the caller.
