# RuleDSL C API Errors

This page describes the stable public error contract for SDK consumers.

## Error categories

- User/integration errors: invalid arguments, missing required fields, contract misuse.
- Artifact errors: compile/verify/bytecode package failures.
- Engine/runtime errors: deterministic runtime failures mapped to stable API codes.

## Rules for callers

- Always branch on `AXErrorCode` values.
- Do not parse human-readable strings for control flow.
- Use `ax_error_to_string(code)` for stable symbolic names.
- Use `ax_last_error_detail_utf8` for diagnostics/logging.

## Diagnostic APIs

- `const char* ax_error_to_string(AXErrorCode code)`
- `AXErrorCode ax_last_error_code(void)`
- `size_t ax_last_error_detail_utf8(char* buf, size_t cap)`
- `void ax_clear_last_error(void)`

`ax_last_error_detail_utf8` behavior:

- returns required bytes excluding trailing NUL
- `cap == 0` performs size query only
- when `cap > 0` and `buf != NULL`, output is always NUL-terminated

## Minimal usage (C)

```c
AXErrorCode code = ax_eval_bytecode(compiler, &bc, fields, field_count, &opts, &decision, err, sizeof(err));
if (code != AX_ERR_OK) {
    char detail[256];
    size_t needed = ax_last_error_detail_utf8(detail, sizeof(detail));
    printf("error=%s (%d) detail=%s needed=%zu\n", ax_error_to_string(code), (int)code, detail, needed);
}
```
