# Release Notes Template (Bundle Level)

## Release

- Product: RuleDSL SDK
- Bundle type: `<Evaluation|Commercial>`
- Release version: `<x.y.z>`
- Compiler version: `<ruledslc --version>`
- Engine version: `<engine version>`

## Included

- Public headers (`include/`)
- Engine and compiler binaries (`bin/`)
- Public docs (`docs/`)
- Examples (`examples/`)
- Deterministic manifests (`manifests/`)

## Not Included

- Engine source code
- Compiler source code
- Debug symbols (`.pdb`)
- Build directories and CMake metadata

## Supported Platforms

- `<platform list>`

## Upgrade / Compatibility

Use this boilerplate:

```text
This release is compatible with the versions listed in docs/compatibility_matrix.md.
Compile with the included ruledslc version and verify every .axbc using `ruledslc verify`
before evaluation. Run `ax_check_bytecode_compatibility` before calling evaluation APIs.
```

## Verification Instructions

1. Validate `manifests/HASHES.txt`.
2. Confirm `ruledslc --version` matches release records.
3. Run compile -> verify -> evaluate smoke flow.

## Known Limitations

- Signature policy may be optional depending on delivery tier.
- License status may report stub/placeholder values in evaluation distributions.