# RuleDSL SDK Release Notes

## What is included

- Public SDK headers (`include/`)
- Compiled engine and compiler binaries (`bin/`)
- Public operational and language docs (`docs/`)
- Example programs and rule files (`examples/`)
- Deterministic delivery manifests (`manifests/`)

## What is not included

- Engine source code
- Compiler source code
- Debug build artifacts and private tooling

## Supported platforms

See the current distribution packet and `docs/compatibility_matrix.md`.

## Upgrade / Compatibility

Use this boilerplate for each release:

```text
This release follows the compatibility matrix published in docs/compatibility_matrix.md.
Compile rules with the provided ruledslc version and run ruledslc verify on each bytecode artifact.
Before evaluation, call ax_check_bytecode_compatibility and proceed only when status is OK.
```

## Verification instructions

1. Validate `manifests/HASHES.txt` before running binaries.
2. Confirm `ruledslc --version` matches release metadata.
3. Run the compile -> verify -> evaluate smoke path.

## Known limitations

- Signature verification policy may differ by distribution tier.
- Evaluation bundles may use license status placeholder outputs.