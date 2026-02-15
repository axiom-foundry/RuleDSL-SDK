# SDK Capabilities Fingerprint

Use `ax_version_string()` and `ax_capabilities()` to feature-detect SDK behavior at runtime.

## API

- `ax_version_string()` returns a library-owned static string.
- `ax_capabilities(AXCapabilitiesV1* out)` fills capability flags for the current library build.

## Caller Contract

- Initialize with `AX_CAPABILITIES_V1_INIT` or `AX_INIT_AXCapabilitiesV1`.
- Keep `struct_size` and `version` valid before calling `ax_capabilities`.
- Do not free the pointer returned by `ax_version_string`.

## Feature Detection Example

```c
AXCapabilitiesV1 caps = AX_CAPABILITIES_V1_INIT;
if (ax_capabilities(&caps) == AX_ERR_OK) {
    if (caps.has_ex2) {
        /* safe to use ax_eval_bytecode_ex2 */
    }
}
```

## Current V1 Values

- `abi_level = 1`
- `has_ex2 = 1`
- `replay_schema = 1`
