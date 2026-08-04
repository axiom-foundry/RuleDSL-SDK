# Release Bundle Tooling

## `build_bundle.ps1`

Assembles a deterministic SDK delivery bundle.

### Usage

```powershell
pwsh Tools/release_bundle/build_bundle.ps1 \
  -EngineBin <path-to-engine-binary> \
  -CompilerBin <path-to-ruledslc> \
  -EngineSourceSha <exact-lowercase-40-hex-engine-commit> \
  -SdkSourceSha <exact-lowercase-40-hex-sdk-commit> \
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
  `engine_source_sha` and `sdk_source_sha` are mandatory exact lowercase 40-hex
  commit identities; engine/package/language versions remain separate fields.
- `HASHES.txt` uses canonical lines: `<sha256>  <relative_path>` sorted by path.
- `TOOLCHAIN.txt` records `ruledslc --version`, engine version, both full source
  SHAs, and the script revision.
- `LICENSE_STATUS.txt` records the bundle license: `LICENSE=PolyForm-Free-Trial-1.0.0` / `TYPE=EVALUATION` for evaluation bundles, or the executed-commercial-agreement reference for commercial bundles.
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
- strict relative paths: no absolute/backslash/empty/repeated/`.`/`..` aliases,
- no reparse points or symbolic links inside the bundle,
- sorted `HASHES.txt` format,
- SHA256 verification for every listed file,
- exact parity between actual files, `MANIFEST.json` `file_list`, and
  `HASHES.txt` paths; only `manifests/HASHES.txt` itself is excluded.

## CI fixture

A public fixture is available at:

`Tools/release_bundle/fixtures/min_bundle/`

This fixture allows CI to validate layout audit behavior without private binaries.
`test_audit_bundle_layout.ps1` copies it into isolated temporary directories and
proves the valid case plus traversal/dot-segment, unlisted-extra, missing-file and
hash-mismatch failures. Fixture source SHAs validate the schema only; the empty
fixture binaries are not release artifacts or evidence that either SHA reproduces
published v1.0.2 bytes.

## Reviewed engine source pin

`docs/distribution/engine_source_sha.txt` is the only engine source ref accepted by
both bundle workflows and the canonical mirror gate. It contains one exact
lowercase 40-hex commit. To update it:

1. Review the intended private-engine commit and its engine CI/evidence.
2. Change the pin in an SDK pull request; do not add a workflow input or branch/tag
   override.
3. Let `verify-canonical` prove the mirrored SDK artifacts against that checkout.
4. Merge the SDK change before manually building or pushing a release tag. Manual
   and tag builds read the pin from the checked-out SDK commit/tag and verify the
   private checkout's `HEAD` before configure/build.

The pin and provenance fields govern future bundle builds. They do not change or
claim byte reproduction for already-published v1.0.2 engine bundles.

## Linux bundle workflow (`.github/workflows/bundle-linux.yml`)

Produces a **real Linux delivery bundle** (with `bin/` populated) in CI, so the
SDK ships a runnable `ruledslc` executable and `libruledsl_capi.so` for Linux —
not just source.

What it does:

1. Checks out this (public) SDK repo and the private engine repo
   (`axiom-foundry/RuleDSL`).
2. Builds the engine on `ubuntu-24.04` with the same `Release` + Ninja path the
   engine CI runs green, building only `ruledslc` and `axiom_ruledsl_c_shared`
   (output `libruledsl_capi.so`).
3. Smoke-tests the binaries (`ruledslc --version`, an end-to-end compile +
   verify, and an ELF check on the `.so`).
4. Runs `build_bundle.ps1` to assemble a deterministic bundle with `bin/`
   populated, then `audit_bundle_layout.ps1` to validate it.
5. Uploads `RuleDSL-SDK-<tag>-linux-x86_64.{tar.gz,zip}` + `SHA256SUMS.txt` as a
   workflow artifact, and attaches them to the GitHub release on `v*.*.*` tags.

### Required secret

| Secret | Purpose |
|--------|---------|
| `ENGINE_REPO_TOKEN` | PAT used to check out the private engine source. Classic PAT with `repo` scope, or a fine-grained token with **Contents: read** on `axiom-foundry/RuleDSL`. Add under *Settings → Secrets and variables → Actions*. |

### Triggers

- **Manual** (`workflow_dispatch`): choose only `bundle_type`
  (`Evaluation`/`Commercial`). The engine commit always comes from the reviewed
  SDK-tree pin. Outputs land as a workflow artifact.
- **Tag push** (`v*.*.*`): the bundle archives are additionally attached to the
  GitHub release (alongside the source archives from `release.yml`).

### Note on local builds

A native build on macOS produces a Mach-O object, **not** a Linux ELF. To
produce a genuine Linux binary locally you would need Docker/a Linux container
or a cross toolchain; this workflow uses GitHub's Linux runners instead, which
matches the determinism-critical "CI is authoritative" build model.