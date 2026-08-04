# Distribution Model and Release Artifact Structure

## Public-facing summary

This document defines the public release artifact model for controlled RuleDSL SDK distribution.

## Release principles

- Versioned artifact sets are the delivery unit.
- Customers SHOULD verify hashes before integration.
- Release archives ship with `SHA256SUMS.txt`, and bundles include a per-file `manifests/HASHES.txt` for integrity verification.

## Canonical release structure

```text
RuleDSL-<version>/
  bin/
  include/
  docs/
  examples/
  bindings/
  LICENSE
  NOTICE
  manifests/
    MANIFEST.json
    HASHES.txt
    TOOLCHAIN.txt
    LICENSE_STATUS.txt
```

- `bin/`: runtime library and the `ruledslc` compiler
- `include/`: public headers
- `bindings/`: Python and C# bindings
- `manifests/MANIFEST.json`: deterministic release metadata
- `manifests/HASHES.txt`: authoritative in-bundle hash list

## `manifests/MANIFEST.json` (deterministic metadata)

Fields (deterministic key order, written by `Tools/release_bundle/build_bundle.ps1`):

- `bundle_type`
- `created_by`
- `ruledslc_version`
- `engine_version`
- `engine_source_sha` (exact lowercase 40-hex private-engine commit)
- `sdk_source_sha` (exact lowercase 40-hex SDK commit)
- `lang_version`
- `axbc_version`
- `abi_level`
- `file_list` (relative, forward-slash, sorted)

`manifests/HASHES.txt` is the authoritative in-bundle integrity record; `MANIFEST.json` does not embed hashes.

## `manifests/HASHES.txt` format

Canonical line format (two spaces between hash and path):

```text
<sha256>  <relative_path>
```

Requirements (enforced by `Tools/release_bundle/audit_bundle_layout.ps1`):

- covers every bundle file except `manifests/HASHES.txt` itself,
- entries sorted by `<relative_path>`,
- paths are strict relative forward-slash paths with no `.`/`..`, empty,
  repeated, backslash, absolute, or alias segments,
- exact parity with actual bundle files; only `manifests/HASHES.txt` excludes
  itself,
- generated at bundle-assembly time and verified before rollout.

A separate `SHA256SUMS.txt` over the outer `.tar.gz`/`.zip` release archives is produced by the Linux release workflow (`.github/workflows/bundle-linux.yml`).

## Upgrade and rollback

Upgrade:

1. verify hashes,
2. verify compatibility (`docs/version_policy.md`, `docs/compatibility_matrix.md`),
3. stage deployment,
4. keep previous release folder intact.

Rollback:

1. switch to previous versioned folder,
2. confirm version identity,
3. run smoke validation before restoring traffic.

## Distribution channels

- **Public evaluation bundles:** versioned assets on
  [GitHub Releases](https://github.com/axiom-foundry/RuleDSL-SDK/releases),
  distributed under the evaluation license recorded in each bundle's
  `manifests/LICENSE_STATUS.txt`.
- **Commercial or customer-specific bundles:** direct vendor delivery or a
  private secure delivery link under the applicable agreement.

Availability through a public release channel does not grant production-use
rights. For public evaluation bundles, the SDK repository's `LICENSE` governs
and `manifests/LICENSE_STATUS.txt` identifies the bundle type. For commercial
bundles, the executed agreement governs.

## Not included by default

- source code,
- debug symbols unless explicitly provided,
- non-contract preview features.

## References

- `docs/version_policy.md`
- `docs/support_policy.md`
- `docs/bytecode_lifecycle.md`
- `docs/distribution/customer_verification.md`
