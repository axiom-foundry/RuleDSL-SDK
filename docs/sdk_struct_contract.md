# SDK Struct Contract (C API)

## Inventory of public structs

| Struct | Fields (in order) | Public API usage | Allocation / ownership |
| --- | --- | --- | --- |
| `AXCompiler` (opaque handle) | Opaque/incomplete type in header | Passed by pointer in compiler, compile, and eval APIs | Library allocates (`ax_compiler_create`), caller releases (`ax_compiler_destroy`) |
| `AXValue` | `type`, `number`, `text`, `boolean`, `currency` | Passed by value as `AXField.value` (nested) | Caller-owned input data |
| `AXField` | `name`, `value` | Passed by pointer (`const AXField*`) + count in eval APIs | Caller-owned input array |
| `AXBytecode` | `data`, `size` | Passed by pointer in compile/eval/free APIs | Struct is caller-owned; `data` from `ax_compile_to_bytecode` is library-allocated and must be released with `ax_bytecode_free` |
| `AXEvalOptions` | `struct_size`, `trace_cb`, `trace_user`, `reserved[4]` | Passed by pointer (`const AXEvalOptions*`) to eval APIs | Caller-owned options struct |
| `AXDecision` | `struct_size`, `matched`, `action_type`, `amount`, `currency`, `window_count`, `window_unit`, `rule_name`, `reserved[4]` | Passed by pointer (`AXDecision*`) to eval APIs | Caller-owned result struct; SDK may allocate string members, caller clears with `ax_decision_reset`/`ax_decision_free` |

## ABI contract rules

- Never reorder existing fields.
- Never remove existing fields.
- Existing struct numeric/offset layout is frozen once published.
- New capacity is added by tail extension when ABI-safe.

## `struct_size` contract

- Caller sets `struct_size = sizeof(struct_type)` before API call.
- API accepts equal or larger sizes.
- API returns `AX_ERR_BAD_STRUCT_SIZE` when `struct_size` is smaller than the minimum supported size.

## C initialization examples

```c
AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
AXDecision out = AX_DECISION_INIT;
```

Reset after use:

```c
ax_decision_reset(&out);
```
