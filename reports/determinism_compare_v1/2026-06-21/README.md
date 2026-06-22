# Determinism comparison reports — 2026-06-21

This directory holds the **cross-platform comparison reports** for the published
determinism evidence set dated `2026-06-21`. Each report records a Windows-x64 vs
Linux-x64 byte comparison of a determinism case and is the artifact behind the
"recompute the hashes yourself" claim.

There is one `comparison.json` per DET case:

| Report | DET case | What it compares |
| --- | --- | --- |
| `DET-001/windows-x64__linux-x64/comparison.json` | DET-001 (standard decision-output path) | Windows-x64 bundle vs Linux-x64 bundle |
| `DET-003/windows-x64__linux-x64/comparison.json` | DET-003 (deterministic error path) | Windows-x64 bundle vs Linux-x64 bundle |

Each report (schema `determinism-bundle-compare-v2`) records `status: "pass"`,
`equal_output: true`, and an `output_bin_sha256` that is **identical** on both
platforms:

- DET-001 `output_bin_sha256` = `f3714ba24ad7a84218874bff096eab721bd67bcd5641cd45d2973fd86d55c5e1`
- DET-003 `output_bin_sha256` = `9b0dd8f9caeadd8e6ed1fabd65305041bc5d518cbf5716f54178691d88727a65`

## Source bundles (committed here)

The comparison reports are derived from the four evidence bundles committed under
[`reports/determinism_v1_0/2026-06-21/`](../../determinism_v1_0/2026-06-21/). Each bundle
holds `inputs/`, `outputs/`, an `environment/` fingerprint, a `manifest.json`, and a
`SHA256SUMS.txt`:

| Bundle directory | Platform | DET case |
| --- | --- | --- |
| `reports/determinism_v1_0/2026-06-21/windows-x64/ci-windows/` | Windows-x64 | DET-001 |
| `reports/determinism_v1_0/2026-06-21/linux-x64/ci-linux/` | Linux-x64 | DET-001 |
| `reports/determinism_v1_0/2026-06-21/windows-x64/ci-windows-det003/` | Windows-x64 | DET-003 |
| `reports/determinism_v1_0/2026-06-21/linux-x64/ci-linux-det003/` | Linux-x64 | DET-003 |

### Note on `bundle_b_rel`

Each `comparison.json` records `bundle_b_rel` as `downloaded/linux/ci-linux[-det003]`.
That is the **compare-time source path** of bundle B: during the cross-platform compare
job the Linux bundle was downloaded into a working directory before being compared
against the Windows bundle (`bundle_a_rel`). It is an honest record of where bundle B
was read from at compare time, not a committed path. The committed equivalent of that
same Linux bundle lives here under
`reports/determinism_v1_0/2026-06-21/linux-x64/ci-linux[-det003]/` — its
`outputs/<DET>_output.bin` hashes byte-for-byte to the `output_bin_sha256` values above,
so the comparison is fully reproducible from committed artifacts.

## Recompute it yourself

All paths below are repo-relative; run from the repository root. For each DET case,
hash both platforms' decision output and confirm they equal each other **and** the
`output_bin_sha256` recorded in that case's `comparison.json`:

```sh
# DET-001 — standard decision-output path
sha256sum reports/determinism_v1_0/2026-06-21/linux-x64/ci-linux/outputs/DET-001_output.bin
sha256sum reports/determinism_v1_0/2026-06-21/windows-x64/ci-windows/outputs/DET-001_output.bin
# both MUST equal f3714ba24ad7a84218874bff096eab721bd67bcd5641cd45d2973fd86d55c5e1

# DET-003 — deterministic error path
sha256sum reports/determinism_v1_0/2026-06-21/linux-x64/ci-linux-det003/outputs/DET-003_output.bin
sha256sum reports/determinism_v1_0/2026-06-21/windows-x64/ci-windows-det003/outputs/DET-003_output.bin
# both MUST equal 9b0dd8f9caeadd8e6ed1fabd65305041bc5d518cbf5716f54178691d88727a65
```

Then verify each bundle's internal integrity against its checksum manifest:

```sh
( cd reports/determinism_v1_0/2026-06-21/linux-x64/ci-linux        && sha256sum -c SHA256SUMS.txt )
( cd reports/determinism_v1_0/2026-06-21/linux-x64/ci-linux-det003 && sha256sum -c SHA256SUMS.txt )
( cd reports/determinism_v1_0/2026-06-21/windows-x64/ci-windows        && sha256sum -c SHA256SUMS.txt )
( cd reports/determinism_v1_0/2026-06-21/windows-x64/ci-windows-det003 && sha256sum -c SHA256SUMS.txt )
```

A matching pair of hashes (equal to each other and to `comparison.json`) demonstrates
cross-platform byte-identity; a clean `sha256sum -c` run demonstrates each bundle is
internally intact.

## Scope

This evidence proves **cross-platform** (Windows-x64 ↔ Linux-x64) byte-identical
determinism. Independent **multi-host** reproducibility (multiple machines of the same
platform) remains future work.
