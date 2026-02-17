# Distribution Model and Release Artifact Structure

## Public-facing summary

This document defines the public release artifact model for controlled RuleDSL SDK distribution.

## Release principles

- Versioned artifact sets are the delivery unit.
- Customers SHOULD verify hashes before integration.
- Signing is optional by policy and may be required per delivery tier.

## Canonical release structure

```text
RuleDSL-<version>/
  bin/
  include/
  docs/
  examples/            (optional)
  manifest.json
  SHA256SUMS.txt
```

- `bin/`: runtime libraries
- `include/`: public headers
- `manifest.json`: release metadata
- `SHA256SUMS.txt`: authoritative hash list

## `manifest.json` (informational)

Required fields:

- `product_name`
- `version`
- `build_date`
- `supported_abi_level`
- `bytecode_schema_version`
- `supported_os`
- `supported_arch`
- `artifact_hashes`

`SHA256SUMS.txt` remains authoritative for integrity checks.

## `SHA256SUMS.txt` format

Canonical line format:

```text
<sha256>  <relative_path>
```

Requirements:

- include distributed binaries and headers,
- generated at packaging time,
- verified before rollout.

## Upgrade and rollback

Upgrade:

1. verify hashes,
2. verify compatibility (`docs/version_policy.md`),
3. stage deployment,
4. keep previous release folder intact.

Rollback:

1. switch to previous versioned folder,
2. confirm version identity,
3. run smoke validation before restoring traffic.

## Distribution channels

- direct vendor delivery,
- private secure delivery link,
- no public download channel.

## Not included by default

- source code,
- debug symbols unless explicitly provided,
- non-contract experimental features.

## References

- `docs/version_policy.md`
- `docs/support_policy.md`
- `docs/bytecode_lifecycle.md`
- `docs/signing_policy.md`