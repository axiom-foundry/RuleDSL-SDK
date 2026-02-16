# C API Ownership and Lifetime Contract

This document is the authoritative ownership and lifetime contract for the public C API in `include/axiom/ruledsl_c.h`.

## Ownership Map

| API | Returns / writes | Ownership after call | How to free / release |
| --- | --- | --- | --- |
| `ax_compiler_create()` | `AXCompiler*` | Caller owns compiler handle | `ax_compiler_destroy(compiler)` |
| `ax_compiler_destroy(AXCompiler*)` | none | Consumes compiler handle | Do not reuse pointer after destroy |
| `ax_compile_to_bytecode(..., AXBytecode* out, ...)` | `out->data`, `out->size` | Caller owns `AXBytecode.data` buffer | `ax_bytecode_free(&bytecode)` |
| `ax_bytecode_free(AXBytecode*)` | none | Releases `bytecode->data`, zeros size | Safe to call with null / empty buffer |
| `ax_eval_bytecode(..., AXDecision* out_decision, ...)` | `out_decision` fields and optional owned strings (`currency`, `window_unit`, `rule_name`) | Caller owns `AXDecision` struct; library allocates owned strings inside it | `ax_decision_reset(&decision)` before reuse/discard (`ax_decision_free` is compatibility alias) |
| `ax_decision_reset(AXDecision*)` | none | Frees owned decision strings, clears payload, keeps struct caller-owned | No further free needed for cleared members |
| `ax_decision_free(AXDecision*)` | none | Backward-compatible alias of `ax_decision_reset` | Same as reset |
| `ax_free(void*)` | none | Generic free helper for API-owned heap pointers returned by SDK APIs | Call only on pointers allocated by SDK |
| Eval/compile `err` outputs | writes into caller buffer | Caller owns buffer | Caller allocates and manages lifetime |
| Eval/compile inputs (`AXField*`, `AXValue.text`, `AXValue.currency`, options structs) | read-only during call | Caller owns inputs | Keep valid for call duration |

## Core Rules

1. **Caller owns all public structs** (`AXBytecode`, `AXDecision`, and options structs).
2. **Library never frees caller struct memory**; reset/free APIs only deep-clear owned members.
3. **Decision string fields are SDK-owned allocations** after successful eval and must be released via reset/free APIs.
4. **Reset invalidates prior decision string pointers** by freeing and setting them to `NULL`.
5. **Reuse-safe pattern is mandatory**: call `ax_decision_reset` before reusing decision structs.
6. **`ax_decision_free` is compatibility behavior**; it is not a struct destructor.
7. **Compiler handle lifetime is explicit**: create once, build, use, then destroy.
8. **Input pointer lifetimes are call-scoped**: keep all input strings and arrays valid until API call returns.

## C Usage Example

```c
AXCompiler* compiler = ax_compiler_create();
char err[256] = {0};
AXBytecode bc = {0};
AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
AXDecision decision = AX_DECISION_INIT;

/* ... build compiler and compile bytecode ... */
AXErrorCode code = ax_eval_bytecode(compiler, &bc, fields, field_count, &opts, &decision, err, sizeof(err));
if (code == AX_ERR_OK) {
    /* use decision.currency/window_unit/rule_name */
}

ax_decision_reset(&decision);
ax_bytecode_free(&bc);
ax_compiler_destroy(compiler);
```
