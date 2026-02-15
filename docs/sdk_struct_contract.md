# SDK Struct Contract (C API)

## Inventory of public structs

| Struct | Fields (in order) | Public API usage | Allocation / ownership |
| --- | --- | --- | --- |
| `AXCompiler` (opaque handle) | Opaque/incomplete type in header | Passed by pointer in `ax_compiler_create`, `ax_compiler_destroy`, `ax_compiler_build`, `ax_compile_to_bytecode`, `ax_eval_bytecode`, `ax_eval_bytecode_ex2` | Library allocates (`ax_compiler_create`), caller releases (`ax_compiler_destroy`) |
| `AXValue` | `type`, `number`, `text`, `boolean`, `currency` | Passed by value as `AXField.value` (nested) | Caller-owned input data |
| `AXField` | `name`, `value` | Passed by pointer (`const AXField*`) + count in eval APIs | Caller-owned input array |
| `AXBytecode` | `data`, `size` | Passed by pointer in compile/eval/free APIs | Struct is caller-owned; `data` buffer from `ax_compile_to_bytecode` is library-allocated and must be released with `ax_bytecode_free` |
| `AXEvalOptions` (legacy) | `struct_size`, `trace_cb`, `trace_user`, `reserved[4]` | Passed by pointer (`const AXEvalOptions*`) to `ax_eval_bytecode` | Caller-owned options struct |
| `AXDecision` (legacy) | `struct_size`, `matched`, `action_type`, `amount`, `currency`, `window_count`, `window_unit`, `rule_name`, `reserved[4]` | Passed by pointer (`AXDecision*`) to `ax_eval_bytecode` | Caller-owned result struct; SDK may allocate string members, caller clears with `ax_decision_reset`/`ax_decision_free` |
| `AXEvalOptionsV2` | `struct_size`, `version`, `trace_cb`, `trace_user`, `reserved[4]` | Passed by pointer (`const AXEvalOptionsV2*`) to `ax_eval_bytecode_ex2` | Caller-owned options struct |
| `AXDecisionV2` | `struct_size`, `version`, `matched`, `action_type`, `amount`, `currency`, `window_count`, `window_unit`, `rule_name`, `reserved[4]` | Passed by pointer (`AXDecisionV2*`) to `ax_eval_bytecode_ex2` | Caller-owned result struct; SDK may allocate string members, caller clears with `ax_decision_reset_v2` |

## ABI contract rules

- Never reorder existing fields.
- Never remove existing fields.
- Existing struct numeric/offset layout is frozen once published.
- New capacity is added by tail extension when ABI-safe.
- If adding head metadata (`version`) would break existing layout, define a `V2` struct and new entry point.

## `struct_size` contract

- Caller sets `struct_size = sizeof(struct_type)` before API call.
- API accepts equal or larger sizes.
- API returns `AX_ERR_BAD_STRUCT_SIZE` when `struct_size` is smaller than the minimum supported size.
- This allows forward-compatible callers with larger structs.

## Version negotiation model

- V1 legacy structs remain supported by legacy APIs.
- V2 structs include a `version` field.
- Current supported V2 version is `1`.
- Unsupported V2 version returns `AX_ERR_INVALID_ARGUMENT`.
- Future versions must preserve existing prefix layout and add fields only in documented extension space.

## C initialization examples

```c
AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
AXDecision out = AX_DECISION_INIT;

AXEvalOptionsV2 opts_v2;
AXDecisionV2 out_v2;
AX_INIT_AXEvalOptionsV2(&opts_v2);
AX_INIT_AXDecisionV2(&out_v2);
```

Reset after use:

```c
ax_decision_reset(&out);
ax_decision_reset_v2(&out_v2);
```