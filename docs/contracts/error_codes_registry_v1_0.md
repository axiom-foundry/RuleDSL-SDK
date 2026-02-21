# AXErrorCode Registry (v1.0)

This document defines the stable public error-code contract for RuleDSL SDK v1.0.

## 1. Stability contract

- `AXErrorCode` numeric values are part of the public ABI contract and MUST remain stable within major version `1.x`.
- Existing code names and numeric values MUST NOT be renumbered or repurposed.
- New error codes MAY be added in minor/patch versions, but existing meanings MUST NOT change.
- Consumers MUST treat unknown numeric codes as `unknown error` and MUST NOT assume undefined values are success.

## 2. Error surface separation

- Error code (`AXErrorCode`): stable control-flow surface and contractual.
- Error message bytes (`err` buffers, diagnostic strings): best-effort diagnostics and NOT contractual unless explicitly versioned by a future contract.

## 3. Registry table (current v1.0 surface)

| Code name | Numeric value | Semantic meaning | Message bytes stability |
| --- | ---: | --- | --- |
| `AX_ERR_OK` | 0 | Evaluation completed successfully. No error condition. | N/A |
| `AX_ERR_INVALID_ARGUMENT` | 1 | Caller-provided arguments violate API preconditions (null/invalid pointers, invalid counts, or contract misuse). | Not guaranteed |
| `AX_ERR_COMPILE` | 2 | Compiler/build step failed for provided rule/bytecode compilation context. | Not guaranteed |
| `AX_ERR_VERIFY` | 3 | Bytecode or artifact verification failed (integrity/format validation path). | Not guaranteed |
| `AX_ERR_MISSING_NOW_UTC_MS` | 4 | Required `now_utc_ms` input field is missing in evaluation input. | Not guaranteed |
| `AX_ERR_NOW_UTC_MS_NOT_NUMBER` | 5 | `now_utc_ms` is present but not a numeric value. | Not guaranteed |
| `AX_ERR_NON_FINITE` | 6 | Non-finite numeric input or intermediate value rejected by numeric contract. | Not guaranteed |
| `AX_ERR_DIV_ZERO` | 7 | Division-by-zero condition reached in deterministic evaluation path. | Not guaranteed |
| `AX_ERR_CONCURRENT_COMPILER_USE` | 8 | Concurrent or invalid compiler object usage detected. | Not guaranteed |
| `AX_ERR_LIMIT_EXCEEDED` | 9 | Configured engine/runtime limits were exceeded during compile or evaluation. | Not guaranteed |
| `AX_ERR_BAD_STRUCT_SIZE` | 10 | Caller passed a struct with unsupported or too-small `struct_size`. | Not guaranteed |
| `AX_ERR_RUNTIME` | 11 | Runtime failure not covered by a more specific public code. | Not guaranteed |

## 4. Consumer handling requirements

- Consumers SHOULD branch on numeric error code and stable symbolic name.
- Consumers MUST NOT parse error message text/bytes for business logic.
- Consumers SHOULD log diagnostic bytes/strings for troubleshooting only.
