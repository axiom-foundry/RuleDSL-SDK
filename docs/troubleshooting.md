# RuleDSL SDK — Troubleshooting Guide

This guide covers the most common integration issues and how to resolve them without vendor support.

> **Rule of thumb**: Always branch on `AXErrorCode` numeric values. Use `ax_error_to_string()` for logging and `ax_last_error_detail_utf8()` for diagnostic context. Never parse error message text for control flow.

---

## 1. `AX_ERR_MISSING_NOW_UTC_MS` (code 4)

**Symptom**: Evaluation returns error code 4 immediately.

**Cause**: The engine requires a `now_utc_ms` field in every evaluation call. This is by design — the engine never reads wall-clock time internally to preserve determinism.

**Fix**:
```c
AXField fields[] = {
    { "now_utc_ms", { AX_VALUE_NUMBER, .number = 1700000000000.0 } },
    // ... your other fields
};
```

**Important**: The value must be epoch milliseconds as a `NUMBER` type, not a string. Use your host application's clock to inject the current time.

---

## 2. `AX_ERR_NOW_UTC_MS_NOT_NUMBER` (code 5)

**Symptom**: You provide `now_utc_ms` but still get an error.

**Cause**: The `now_utc_ms` field exists in your input but its `AXValueType` is not `AX_VALUE_NUMBER`.

**Fix**: Ensure the field value has `.type = AX_VALUE_NUMBER` and the timestamp is in `.number`:
```c
AXValue now_val = { .type = AX_VALUE_NUMBER, .number = (double)epoch_ms };
```

Do NOT pass it as a string like `"1700000000000"`.

---

## 3. `AX_ERR_BAD_STRUCT_SIZE` (code 10)

**Symptom**: Any API call returns error code 10.

**Cause**: The `struct_size` field in `AXEvalOptions`, `AXDecision`, or `AXCompatibilityInfo` does not match what the library expects. This usually means you forgot to use the init macros.

**Fix**: Always initialize structs with the provided macros:
```c
AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
AXDecision    dec  = AX_DECISION_INIT;
AXCompatibilityInfo info = AX_COMPATIBILITY_INFO_INIT;
```

These macros set `struct_size = sizeof(...)` and zero-initialize reserved fields. Never construct these structs manually with `memset` or brace initialization unless you explicitly set `struct_size`.

---

## 4. `AX_ERR_COMPILE` (code 2)

**Symptom**: `ax_compile_to_bytecode()` or `ax_compiler_build()` returns error code 2.

**Cause**: The rule source text has a syntax or semantic error.

**Fix**:
1. Check the `err` buffer you passed — it contains the compile error message.
2. Common syntax issues:
   - Missing semicolons after `when` or `then` clauses
   - Unclosed braces in rule blocks
   - Unsupported keywords or operators for language version 0.9
3. Validate your `.rule` file with the CLI first:
   ```
   ruledslc compile rules.rule -o rules.axbc --lang 1.0 --target axbc3
   ```
   The CLI will print the exact line and column of the error.

---

## 5. `AX_ERR_VERIFY` (code 3)

**Symptom**: `ax_check_bytecode_compatibility()` returns `AX_STATUS_CORRUPTED_PAYLOAD` or `AX_STATUS_STRUCTURALLY_INVALID`, or `ax_eval_bytecode()` returns error code 3.

**Cause**: The `.axbc` bytecode file is corrupted, truncated, or was produced by an incompatible compiler version.

**Fix**:
1. Verify the bytecode file was not modified after compilation:
   ```
   ruledslc verify rules.axbc
   ```
2. Recompile from source if verification fails.
3. Check the compatibility matrix — ensure your compiler version matches the engine ABI level.
4. Confirm the file was transferred in binary mode (not text mode, which can corrupt bytes on Windows).

---

## 6. `AX_ERR_INVALID_ARGUMENT` (code 1)

**Symptom**: Any API call returns error code 1.

**Cause**: A null pointer, zero count, or other precondition violation was detected.

**Fix**: Check these common mistakes:
- `compiler` is NULL (forgot `ax_compiler_create()` or it failed)
- `ax_compiler_build()` was not called before evaluation
- `fields` pointer is NULL but `field_count > 0`
- `err` buffer is NULL but `err_len > 0`
- `bytecode.data` is NULL or `bytecode.size` is 0

Use `ax_last_error_detail_utf8()` — it will specify which argument was invalid.

---

## 7. `AX_ERR_NON_FINITE` (code 6)

**Symptom**: Evaluation returns error code 6.

**Cause**: A numeric input field contains `NaN`, `+Inf`, or `-Inf`. The engine rejects non-finite values to guarantee deterministic output.

**Fix**: Validate all numeric inputs before passing them to the engine:
```c
#include <math.h>
if (!isfinite(value)) {
    // Handle: use a default, skip this field, or return an error to your caller
}
```

---

## 8. `AX_ERR_DIV_ZERO` (code 7)

**Symptom**: Evaluation returns error code 7.

**Cause**: A rule expression divides by zero (or by a value within epsilon of zero).

**Fix**: This is a **rule logic issue**, not an integration issue. Options:
1. Add a guard condition in your rule: `when divisor != 0 and amount / divisor > threshold`
2. Ensure input data cannot contain zero for divisor fields
3. This is deterministic — the same inputs will always produce this error, making it easy to diagnose

---

## 9. `AX_ERR_CONCURRENT_COMPILER_USE` (code 8)

**Symptom**: Error code 8 appears under load in multi-threaded applications.

**Cause**: The same `AXCompiler*` instance was used from multiple threads simultaneously. `AXCompiler` is NOT thread-safe for concurrent use.

**Fix**: Choose one of these patterns:
- **Per-thread compiler**: Create a separate `AXCompiler` per thread
- **Pool pattern**: Maintain a pool of compiler instances, check out one per evaluation
- **Mutex**: Protect the compiler with a lock (simplest but serializes evaluations)

Note: Concurrent evaluations using *different* compiler instances with *separate* input/output buffers are fully safe.

---

## 10. `AX_ERR_LIMIT_EXCEEDED` (code 9)

**Symptom**: Compilation or evaluation returns error code 9.

**Cause**: The rule exceeded engine safety limits (token count, nesting depth, evaluation fuel, list size, or string length).

**Fix**: Simplify the rule:
- Break deeply nested expressions into multiple rules
- Reduce `IN [...]` list sizes
- Split complex rule programs into smaller compilation units

These limits exist to prevent resource exhaustion and ensure bounded evaluation time.

---

## General Debugging Checklist

If you encounter an unexpected error, follow this sequence:

```c
// 1. Capture the error code
AXErrorCode code = ax_eval_bytecode(...);

// 2. Get the symbolic name
const char* name = ax_error_to_string(code);

// 3. Get diagnostic detail
char detail[512];
ax_last_error_detail_utf8(detail, sizeof(detail));

// 4. Log everything
fprintf(stderr, "[RuleDSL] %s (code=%d): %s\n", name, (int)code, detail);

// 5. Clear the error state
ax_clear_last_error();
```

## Incident Reporting

If self-service resolution fails, prepare this bundle before contacting support:

| Item | How to collect |
|------|----------------|
| SDK version | `ax_version_string()` output |
| OS and architecture | e.g., "Windows 11 x64" or "Ubuntu 22.04 x64" |
| Binary SHA-256 | `sha256sum ruledsl_capi.dll` |
| Bytecode SHA-256 | `sha256sum rules.axbc` |
| Error code + detail | From your log (step 4 above) |
| Minimal repro | Smallest `.rule` file + input fields that trigger the issue |
| Expected vs actual | What you expected and what happened |

See also: [`docs/support_policy.md`](support_policy.md) for severity levels and response targets.
