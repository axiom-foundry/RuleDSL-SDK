# SDK Capabilities Fingerprint

Use `ax_version_string()` as the stable runtime fingerprint.

## API

- `ax_version_string()` returns a library-owned static string.
- `ax_check_bytecode_compatibility()` reports bytecode/ABI compatibility fields (`AXCompatibilityInfo`: `axbc_version`, `lang_major`/`lang_minor`, `minimum_engine_abi`, `flags`).

## Caller Contract

- Initialize `AXCompatibilityInfo` with `AX_COMPATIBILITY_INFO_INIT` (sets `struct_size`) before calling `ax_check_bytecode_compatibility()`, exactly as documented in the shipped header.
- Do not free the pointer returned by `ax_version_string()`.

## Expected Baseline

- `abi_level = 1` (reported as `minimum_engine_abi` in `AXCompatibilityInfo`, and shown as `abi=1` in the `ax_version_string()` fingerprint)
