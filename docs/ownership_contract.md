# C API Ownership and Lifetime Contract

This document is the authoritative ownership and lifetime contract for the public C API in `include/axiom/ruledsl_c.h`. If another document conflicts with this one, this contract takes precedence.

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
| `ax_eval_bytecode_ex2(..., AXDecisionV2* out_decision, ...)` | `out_decision` fields and optional owned strings (`currency`, `window_unit`, `rule_name`) | Caller owns `AXDecisionV2` struct; library allocates owned strings inside it | `ax_decision_reset_v2(&decision_v2)` before reuse/discard |
| `ax_decision_reset_v2(AXDecisionV2*)` | none | Frees owned decision strings, clears payload, keeps struct caller-owned | No further free needed for cleared members |
| `ax_free(void*)` | none | Generic free helper for API-owned heap pointers returned by SDK APIs | Call only on pointers allocated by SDK |
| `ax_compiler_build(..., char* err, size_t err_len)` and eval/compile `err` outputs | writes into caller buffer | Caller owns buffer | Caller allocates and manages lifetime |
| Eval/compile inputs (`AXField*`, `AXValue.text`, `AXValue.currency`, options structs) | read-only during call | Caller owns inputs | Keep valid for call duration |

## Core Rules

1. **Caller owns all public structs** (`AXBytecode`, `AXDecision`, `AXDecisionV2`, options structs).
2. **Library never frees caller struct memory**; reset/free APIs only deep-clear owned members.
3. **Decision string fields are SDK-owned allocations** after successful eval and must be released via reset/free APIs.
4. **Reset invalidates prior decision string pointers** by freeing and setting them to `NULL`.
5. **Reuse-safe pattern is mandatory**: call `ax_decision_reset` / `ax_decision_reset_v2` before reusing decision structs.
6. **`ax_decision_free` is compatibility behavior** for legacy code; it is not a struct destructor.
7. **Compiler handle lifetime is explicit**: create once, build, use, then destroy.
8. **Input pointer lifetimes are call-scoped**: keep all input strings and arrays valid until API call returns.

## Thread-Safety Interaction

- `AXCompiler` is not safe for concurrent use by multiple threads.
- Decision and options structs must be thread-local per in-flight call, or externally synchronized.
- Sharing read-only bytecode buffers is allowed when caller-managed lifetime is respected.

## C Usage Examples

### Legacy flow (`ax_eval_bytecode`)

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

ax_decision_reset(&decision);   /* required before reuse/discard */
ax_bytecode_free(&bc);
ax_compiler_destroy(compiler);
```

### V2 flow (`ax_eval_bytecode_ex2`)

```c
AXEvalOptionsV2 opts_v2;
AXDecisionV2 decision_v2;
AX_INIT_AXEvalOptionsV2(&opts_v2);
AX_INIT_AXDecisionV2(&decision_v2);

AXErrorCode code = ax_eval_bytecode_ex2(
    compiler, &bc, fields, field_count, &opts_v2, &decision_v2, err, sizeof(err));
if (code == AX_ERR_OK) {
    /* use decision_v2.currency/window_unit/rule_name */
}

ax_decision_reset_v2(&decision_v2); /* required before reuse/discard */
```
