# RuleDSL Bundle Standard

## Scope

This document defines the canonical vendor distribution layout for public RuleDSL SDK deliveries.
It covers two bundle types:

1. **Evaluation Bundle**
2. **Commercial Bundle**

Both bundle types use the same deterministic structure and manifest rules.

## Canonical Layout

```text
bundle/
  include/
  bin/
  docs/
  examples/
  manifests/
    MANIFEST.json
    HASHES.txt
    TOOLCHAIN.txt
    LICENSE_STATUS.txt
```

## Inclusion Rules

- `include/`: public headers only.
- `bin/`: distributable binaries only.
- `docs/`: public documentation only.
- `examples/`: public example source and expected outputs.
- `manifests/`: deterministic metadata and hash evidence.

### Allowed `bin/` extensions

- `.exe`
- `.dll`
- `.lib`
- `.so`
- `.a`

## Exclusion Rules (Hard Fail)

The following MUST NOT appear in a delivery bundle:

- debug symbols or debug link artifacts (`.pdb`, `.ilk`, `.idb`),
- build trees (`build/`, `out/`, `cmake-build*/`),
- CMake metadata (`CMakeCache.txt`, `*.cmake`, project files),
- private headers or engine source,
- internal-only docs and test fixtures.

## Deterministic Manifest Rules

- `MANIFEST.json` MUST use deterministic key ordering.
- `MANIFEST.json` `file_list` MUST be relative, forward-slash normalized, and sorted.
- `HASHES.txt` MUST use canonical lines:
  - `<sha256>  <relative_path>`
- `HASHES.txt` entries MUST be sorted by `<relative_path>`.
- `HASHES.txt` MUST NOT include itself.
- No timestamps are emitted in manifests by default.

## Version and Identity Recording

`MANIFEST.json` MUST capture:

- `bundle_type`
- `created_by` (tool identifier only)
- `ruledslc_version`
- `engine_version` (or `UNKNOWN` if unavailable)
- `lang_version`
- `axbc_version`
- `abi_level`
- `file_list`

`TOOLCHAIN.txt` MUST record version lines for compiler and engine.
`LICENSE_STATUS.txt` MUST contain `ruledslc license --status` output (or `LICENSE=UNKNOWN`).