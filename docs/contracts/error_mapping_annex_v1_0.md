# Error Mapping Annex (v1.0)

This annex defines required `AX_ERR_*` mappings for determinism and undefined-behavior detection paths.

## 1. Normative rules

- When a listed condition is detected, the implementation MUST return the required `AX_ERR_*` code in this annex.
- If detection is not possible for a listed condition, behavior remains undefined and MAY surface as `AX_ERR_RUNTIME` only where the Notes column explicitly allows fallback.
- Error message bytes are non-contractual diagnostics unless a future document explicitly versions and freezes a message format.

## 2. Mapping table

| Source ID | Condition | Required code | Notes |
| --- | --- | --- | --- |
| DET-001 | Engine detects an internal determinism contract violation for identical bytecode + normalized input + options. | `AX_ERR_RUNTIME` | Detection is typically conformance-level; runtime detection is not guaranteed. |
| DET-002 | Engine detects disallowed implicit environment dependency (locale/timezone/wall-clock/randomness) in evaluation path. | `AX_ERR_RUNTIME` | Runtime detection is optional; conformance evidence remains primary detection path. |
| DET-003 | Bytecode evaluation path detects invalid or non-verifiable binary artifact input. | `AX_ERR_VERIFY` | Applies to bytecode validity checks on eval/verify boundary. |
| DET-011 | Malformed or truncated bytecode is detected. | `AX_ERR_VERIFY` | Mandatory when detection occurs. |
| DET-012 | Unsupported bytecode format/version is detected in eval path. | `AX_ERR_VERIFY` | Compatibility API may also expose `AX_STATUS_UNSUPPORTED_VERSION`; this annex governs `AX_ERR_*` surface. |
| DET-013 | Non-normalized input is detected (duplicate keys, unstable ordering, malformed canonical payload). | `AX_ERR_INVALID_ARGUMENT` | Detection coverage may be partial; if not detectable, UB remains. |
| DET-014 | Concurrent mutation of input buffers is detected during evaluation. | `AX_ERR_RUNTIME` | Detection is optional; fallback to UB when not detectable. |
| DET-015 | Invalid pointers, invalid sizes, or ownership contract violations are detected at API boundary. | `AX_ERR_INVALID_ARGUMENT` | Mandatory API boundary guard path. |
| DET-016 | Reserved fields are written with non-default values and validation detects misuse. | `AX_ERR_INVALID_ARGUMENT` | If implementation cannot reliably detect, UB remains; fallback to `AX_ERR_RUNTIME` permitted. |
| DET-017 | Required option/input contract violation is detected. | `AX_ERR_INVALID_ARGUMENT` | Use `AX_ERR_MISSING_NOW_UTC_MS` for missing `now_utc_ms`; use `AX_ERR_NOW_UTC_MS_NOT_NUMBER` for wrong type. |
| DET-018 | Unsupported-platform contract violation is detected at runtime. | `AX_ERR_RUNTIME` | Contract scope violation; detection may occur outside API surface. |
| DET-019 | Non-finite numeric input/intermediate is detected. | `AX_ERR_NON_FINITE` | Mandatory when detection occurs. |
| DET-020 | Post-contract API misuse (lifetime/threading/aliasing violation) is detected. | `AX_ERR_RUNTIME` | Detection is optional; UB remains when not detected. |

## 3. Scope note

This annex binds `AX_ERR_*` mappings for v1.0 contract coverage. It does not define structured error tokens; tokenization remains TBD.
