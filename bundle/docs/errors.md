# RuleDSL C API Errors

This page describes the stable public error contract for SDK consumers.

## Error categories

| Band | Range | Category |
|------|-------|----------|
| Success | 0 | No error |
| User/integration | 1–63 | Invalid arguments, missing fields, contract misuse |
| Artifact | 64–127 | Compile, verify, bytecode validation failures |
| Engine/runtime | 128–191 | Deterministic runtime failures |
| Reserved | 192–255 | Future use |

## Rules for callers

- Always branch on `AXErrorCode` numeric values.
- Do not parse human-readable strings for control flow.
- Use `ax_error_to_string(code)` for stable symbolic names.
- Use `ax_last_error_detail_utf8` for diagnostics/logging only.
- Treat any unknown numeric code as "unknown error" — never assume it means success.

## Diagnostic APIs

```c
const char*  ax_error_to_string(AXErrorCode code);      // stable symbolic name
AXErrorCode  ax_last_error_code(void);                   // last error code (thread-local)
size_t       ax_last_error_detail_utf8(char* buf, size_t cap); // diagnostic detail
void         ax_clear_last_error(void);                  // clear thread-local state
```

`ax_last_error_detail_utf8` behavior:

- returns required bytes excluding trailing NUL
- `cap == 0` performs size query only (returns needed size)
- when `cap > 0` and `buf != NULL`, output is always NUL-terminated

## Error code reference

### `AX_ERR_OK` (0) — Success

Evaluation completed successfully. Inspect `AXDecision.matched` and `AXDecision.action_type` for the result.

### `AX_ERR_INVALID_ARGUMENT` (1) — Caller misuse

**What**: A null pointer, invalid count, or API precondition violation was detected.

**Common causes**: NULL compiler, `ax_compiler_build()` not called, NULL fields with non-zero count, NULL bytecode data.

**Action**: Check all pointer arguments and ensure the correct initialization sequence: `create` -> `build` -> `eval`. Call `ax_last_error_detail_utf8()` for specifics.

### `AX_ERR_COMPILE` (2) — Compilation failure

**What**: The rule source text could not be compiled.

**Common causes**: Syntax errors, unsupported language constructs, malformed rule blocks.

**Action**: Check the `err` buffer passed to `ax_compile_to_bytecode()` for the compile error message. Use `ruledslc compile` CLI to validate rules before integration.

### `AX_ERR_VERIFY` (3) — Bytecode verification failure

**What**: The bytecode file is corrupted, truncated, or incompatible.

**Common causes**: File modified after compilation, wrong compiler/engine version pairing, text-mode file transfer corrupting binary data.

**Action**: Run `ruledslc verify <file.axbc>` to validate. Recompile from source if verification fails. Ensure binary transfer mode for `.axbc` files.

### `AX_ERR_MISSING_NOW_UTC_MS` (4) — Required time field absent

**What**: The `now_utc_ms` field was not found in the evaluation input.

**Why**: The engine never reads wall-clock time internally. All time-based logic requires explicit injection to guarantee determinism.

**Action**: Add a field named `"now_utc_ms"` with type `AX_VALUE_NUMBER` containing epoch milliseconds from your host clock.

### `AX_ERR_NOW_UTC_MS_NOT_NUMBER` (5) — Time field wrong type

**What**: The `now_utc_ms` field exists but is not a numeric value.

**Action**: Ensure the field has `.type = AX_VALUE_NUMBER`. Do not pass it as a string.

### `AX_ERR_NON_FINITE` (6) — NaN/Inf rejected

**What**: A numeric input or intermediate value is NaN, +Inf, or -Inf.

**Why**: Non-finite values break deterministic guarantees. The engine rejects them explicitly.

**Action**: Validate all numeric inputs with `isfinite()` before passing them to the engine.

### `AX_ERR_DIV_ZERO` (7) — Division by zero

**What**: A rule expression divided by zero (or near-zero within epsilon).

**Action**: This is a rule logic issue. Add guard conditions in your rules (`when divisor != 0 and ...`) or validate input data.

### `AX_ERR_CONCURRENT_COMPILER_USE` (8) — Thread safety violation

**What**: The same `AXCompiler*` was used from multiple threads simultaneously.

**Action**: Use one compiler per thread, a compiler pool, or protect with a mutex. Concurrent use of *different* compilers with *separate* buffers is safe.

### `AX_ERR_LIMIT_EXCEEDED` (9) — Engine limits hit

**What**: A rule exceeded compile or evaluation safety limits (tokens, depth, fuel, list size, string length).

**Action**: Simplify the rule. Break complex expressions into multiple rules. Reduce `IN [...]` list sizes.

### `AX_ERR_BAD_STRUCT_SIZE` (10) — ABI mismatch

**What**: A struct's `struct_size` field does not match the expected size.

**Action**: Always use init macros: `AX_EVAL_OPTIONS_INIT`, `AX_DECISION_INIT`, `AX_COMPATIBILITY_INFO_INIT`. These set `struct_size` correctly. Never manually construct these structs.

### `AX_ERR_RUNTIME` (11) — Generic runtime error

**What**: A runtime failure not covered by a more specific code.

**Action**: Call `ax_last_error_detail_utf8()` for diagnostic detail. If the issue persists, prepare an incident bundle per the [support policy](support_policy.md).

## Standard error handling pattern

```c
AXErrorCode code = ax_eval_bytecode(compiler, &bc, fields, field_count, &opts, &decision, err, sizeof(err));
if (code != AX_ERR_OK) {
    char detail[512];
    ax_last_error_detail_utf8(detail, sizeof(detail));
    fprintf(stderr, "[RuleDSL] %s (code=%d): %s\n",
            ax_error_to_string(code), (int)code, detail);
    ax_clear_last_error();
    // handle error: log, return, retry, etc.
}
```

## Further reading

- [Troubleshooting guide](troubleshooting.md) — step-by-step resolution for each error
- [Error codes registry (frozen contract)](contracts/error_codes_registry_v1_0.md) — ABI stability rules
- [Support policy](support_policy.md) — incident reporting and response targets
