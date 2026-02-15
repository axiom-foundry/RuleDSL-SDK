# AXErrorCode Registry

## Numeric map (frozen)

| Value | Name | Classification |
| ---: | --- | --- |
| 0 | `AX_ERR_OK` | Success |
| 1 | `AX_ERR_INVALID_ARGUMENT` | Core engine (legacy) |
| 2 | `AX_ERR_COMPILE` | Core engine (legacy) |
| 3 | `AX_ERR_VERIFY` | Core engine (legacy) |
| 4 | `AX_ERR_MISSING_NOW_UTC_MS` | Core engine (legacy) |
| 5 | `AX_ERR_NOW_UTC_MS_NOT_NUMBER` | Core engine (legacy) |
| 6 | `AX_ERR_NON_FINITE` | Core engine (legacy) |
| 7 | `AX_ERR_DIV_ZERO` | Core engine (legacy) |
| 8 | `AX_ERR_CONCURRENT_COMPILER_USE` | Core engine (legacy) |
| 9 | `AX_ERR_LIMIT_EXCEEDED` | Core engine (legacy) |
| 10 | `AX_ERR_BAD_STRUCT_SIZE` | Core engine (legacy) |
| 11 | `AX_ERR_RUNTIME` | Core engine (legacy) |

## Stability policy

- Error-code numbers are a contractual ABI surface.
- Existing numeric values are frozen and must never be renumbered.
- Every new error code must use an explicit numeric assignment.
- Existing public function signatures and return semantics remain unchanged.

## Expansion rules

Reserved ranges for future additions:

- `1-99`: Core engine errors (legacy and future core additions)
- `100-199`: Parser/compile errors
- `200-299`: Runtime evaluation errors
- `300-399`: Memory/resource errors
- `900-999`: Reserved for future expansion

When adding a new code:

1. Choose the correct range.
2. Assign an explicit numeric value.
3. Add the code to this registry table.
4. Keep compile-time guard checks updated.

## Deprecation policy

- Soft deprecation only.
- Deprecated error codes remain defined with the same numeric value.
- Removal or renumbering is not allowed.