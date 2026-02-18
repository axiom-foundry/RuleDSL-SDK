# Release Bundle Tooling

## `build_bundle.ps1`

Assembles a deterministic SDK delivery bundle.

### Usage

```powershell
pwsh Tools/release_bundle/build_bundle.ps1 \
  -EngineBin <path-to-engine-binary> \
  -CompilerBin <path-to-ruledslc> \
  -EngineImportLib <optional-path-to-import-lib> \
  -BundleType Evaluation \
  -EmitManifests:$true \
  -Out <output-folder>
```

### Canonical output

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

### Manifest behavior

- `MANIFEST.json` is emitted with deterministic key order and sorted `file_list`.
- `HASHES.txt` uses canonical lines: `<sha256>  <relative_path>` sorted by path.
- `TOOLCHAIN.txt` records `ruledslc --version`, engine version (if discoverable), and script revision.
- `LICENSE_STATUS.txt` records `ruledslc license --status`; fallback is `LICENSE=UNKNOWN`.
- No timestamps are emitted in manifests by default.

## `audit_bundle_layout.ps1`

Validates bundle structure and deterministic manifest/hash integrity.

### Usage

```powershell
pwsh Tools/release_bundle/audit_bundle_layout.ps1 -BundleDir <bundle-folder>
```

Checks include:
- required directories and manifest files,
- forbidden artifacts (`.pdb`, build dirs, CMake metadata),
- sorted and normalized manifest paths,
- sorted `HASHES.txt` format,
- SHA256 verification for every listed file,
- parity between `MANIFEST.json` `file_list` and `HASHES.txt` paths.

## CI fixture

A public fixture is available at:

`Tools/release_bundle/fixtures/min_bundle/`

This fixture allows CI to validate layout audit behavior without private binaries.