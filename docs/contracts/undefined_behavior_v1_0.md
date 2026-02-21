# Undefined Behavior Boundaries (v1.0)

This document defines strict undefined behavior boundaries for RuleDSL 1.0 determinism scope.

## Undefined behavior list

- [DET-011] Passing malformed or truncated bytecode to evaluation APIs is undefined behavior. Expected error code when detected: `AX_ERR_VERIFY`.
- [DET-012] Passing bytecode with unsupported format/version markers is undefined behavior unless an explicit compatibility error is returned. Expected error code when detected: `AX_ERR_VERIFY` (or compatibility status path in `AXCompatibilityInfo`).
- [DET-013] Supplying non-normalized input (including duplicate keys or unstable field ordering) is undefined behavior for determinism claims. Expected error code when detected: TBD.
- [DET-014] Mutating input buffers concurrently with evaluation is undefined behavior. Expected error code when detected: TBD.
- [DET-015] Passing invalid pointers, invalid sizes, or mismatched ownership across the public C API is undefined behavior. Expected error code when detected: `AX_ERR_INVALID_ARGUMENT`.
- [DET-016] Writing to reserved API fields without explicit version documentation is undefined behavior. Expected error code when detected: TBD.
- [DET-017] Depending on unspecified default option values is undefined behavior when an option is documented as required. Expected error code when detected: `AX_ERR_INVALID_ARGUMENT` (or `AX_ERR_MISSING_NOW_UTC_MS` for missing required time input).
- [DET-018] Invoking evaluation on unsupported platforms is undefined behavior for this contract. Expected error code when detected: TBD.
- [DET-019] Assuming deterministic output from non-finite numeric inputs is undefined behavior unless explicitly documented. Expected error code when detected: `AX_ERR_NON_FINITE`.
- [DET-020] Assuming deterministic behavior after API-level contract violations (lifetime, threading, aliasing) is undefined behavior. Expected error code when detected: TBD.

## Enforcement note

Implementations SHOULD fail fast with stable error codes when undefined behavior is detected, but detection coverage is not guaranteed.

Note: `TBD` mappings require a dedicated AXErrorCode mapping annex that binds each undefined-behavior detection path to a mandatory error/status outcome.
