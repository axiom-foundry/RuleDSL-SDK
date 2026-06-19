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
- Language bindings (`bindings/`)
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

1. Validate the bundle with `sha256sum -c manifests/HASHES.txt` (from the bundle root); for the downloaded archive, validate against the published `SHA256SUMS.txt`.
2. Confirm `ruledslc --version` matches release records.
3. Run compile -> verify -> evaluate smoke flow.

## Known Limitations

- Integrity is verified by SHA256: validate the bundle against `manifests/HASHES.txt`, and validate the release archives against the published `SHA256SUMS.txt`.
- License status may report placeholder values in evaluation distributions (`manifests/LICENSE_STATUS.txt`, and placeholder `LICENSE`/`NOTICE`).