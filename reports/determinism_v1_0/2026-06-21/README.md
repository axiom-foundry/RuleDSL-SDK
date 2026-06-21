# Determinism evidence — published set 2026-06-21

This directory holds a **published, citable** determinism evidence set demonstrating
cross-platform (Windows-x64 ↔ Linux-x64) byte-identical decision output for RuleDSL.

It is committed for auditability; per
[`docs/contracts/published_evidence_index_v1_0.md`](../../../docs/contracts/published_evidence_index_v1_0.md)
evidence bundles are **not** shipped inside SDK release artifacts.

## What is here

| Path | Platform | DET | Notes |
| --- | --- | --- | --- |
| `linux-x64/ci-linux/` | Linux x64 | DET-001 | smoke decision-output bundle |
| `linux-x64/ci-linux-det003/` | Linux x64 | DET-003 | deterministic error-path bundle |
| `windows-x64/ci-windows/` | Windows x64 | DET-001 | smoke decision-output bundle |
| `windows-x64/ci-windows-det003/` | Windows x64 | DET-003 | deterministic error-path bundle |
| `../../determinism_compare_v1/2026-06-21/DET-001/windows-x64__linux-x64/comparison.json` | — | DET-001 | Windows-vs-Linux comparison report |
| `../../determinism_compare_v1/2026-06-21/DET-003/windows-x64__linux-x64/comparison.json` | — | DET-003 | Windows-vs-Linux comparison report |

Each bundle conforms to
[`docs/contracts/determinism_evidence_bundle_v1_0.md`](../../../docs/contracts/determinism_evidence_bundle_v1_0.md)
(`manifest.json`, `SHA256SUMS.txt`, `inputs/`, `outputs/`, `environment/`).

## What it proves

For both DET-001 and DET-003 the comparison report records
`status: "pass"`, `equal_output: true`, and an `output_bin_sha256` that is **identical**
on Windows-x64 and Linux-x64:

- DET-001 `output_bin_sha256` = `f3714ba24ad7a84218874bff096eab721bd67bcd5641cd45d2973fd86d55c5e1`
- DET-003 `output_bin_sha256` = `9b0dd8f9caeadd8e6ed1fabd65305041bc5d518cbf5716f54178691d88727a65`

Both platform bundles are independently reproducible (each `verify-existing` passes); the
windows side is not hash-attested-only.

## Provenance

These bundles were produced by the engine `determinism-evidence-v1.yml` workflow (a publication
run with `date=2026-06-21`) on two distinct CI runners and a Release build, then compared with
`compare_bundles.py`.

What the **committed** artifacts themselves attest: each `environment/platform_fingerprint.json`
records its run's `platform` (`linux-x64` / `windows-x64`), `system`, and Python version; the
cross-platform byte-identity is proven by the matching `output_bin_sha256` values in the comparison
reports. The runner OS images and the workflow run URL are generation context, not part of the
committed evidence. Independent **multi-host** (multiple machines of the same platform)
reproducibility remains future work.

> Note on comparison paths: the comparison reports record `bundle_b_rel` as the run-time download
> path `downloaded/linux/ci-linux[-det003]`; that is the same Linux bundle committed here under
> `linux-x64/ci-linux[-det003]` (the `output_bin_sha256` values match byte-for-byte).

## How to re-verify

Using the engine bundle tool against any bundle directory here:

```text
python generate_det001_bundle.py --verify-existing <bundle-dir>
```

A passing bundle exits `0`. The comparison reports can be re-checked by recomputing the
SHA-256 of each bundle's `outputs/<DET>_output.bin` and confirming the two platforms match.
