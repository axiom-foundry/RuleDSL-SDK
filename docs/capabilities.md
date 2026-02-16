# SDK Capabilities Fingerprint

Use `ax_version_string()` as the stable runtime fingerprint.

## API

- `ax_version_string()` returns a library-owned static string.
- Some builds may also expose a capabilities query API for optional feature detection.

## Caller Contract

- Keep capability structs initialized exactly as documented in the shipped header.
- Do not free the pointer returned by `ax_version_string()`.

## Expected Baseline

- `abi_level = 1`
- `replay_schema = 1` (when replay support is included)
