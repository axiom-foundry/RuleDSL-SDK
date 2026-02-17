# Release Gate

## A) Purpose and when to run

The release gate is a local verifier for a prepared release folder (`RuleDSL-<version>/`).
Run it before any customer delivery step.

The gate validates mandatory release packaging rules defined in `docs/distribution.md`.
If any MUST check fails, the release is not shippable.

## B) Inputs

Required input:

- A prepared release folder path (`--release-dir`) containing release artifacts.

Required output location:

- An explicit output folder path (`--out-dir`).

Example (PowerShell):

```powershell
python Tools/release_gate/release_gate.py --release-dir C:\path\to\RuleDSL-1.0.0 --out-dir reports/release_gate/1.0.0
```

## C) Checklist items (MUST)

The gate enforces the following checks:

1. Required release structure exists:
   - `bin/`
   - `include/`
   - `manifest.json`
   - `SHA256SUMS.txt`
2. `manifest.json` is valid UTF-8 JSON and contains required fields:
   - `product_name`
   - `version`
   - `build_date`
   - `supported_abi_level`
   - `bytecode_schema_version`
   - `supported_os`
   - `supported_arch`
   - `artifact_hashes`
3. `SHA256SUMS.txt` lines follow canonical format:
   - `<sha256>  <relative_path>`
4. Hash verification passes for all entries in `SHA256SUMS.txt`.
5. Minimum coverage requirement holds:
   - all files under `bin/` and `include/` are listed in `SHA256SUMS.txt`.
6. Manifest hash mapping consistency:
   - `manifest.json` `artifact_hashes` MUST match `SHA256SUMS.txt` exactly (same paths and hashes).
7. Version consistency check (if applicable):
   - if folder name matches `RuleDSL-<version>`, manifest `version` MUST equal `<version>`.
8. BOM check (best-effort text hygiene):
   - `manifest.json` and `SHA256SUMS.txt` MUST NOT contain UTF-8 BOM.

Advisory checks (SHOULD):

- `docs/` exists.
- `examples/` exists (optional for release policy).

## D) Outputs

The gate writes two outputs under `--out-dir`:

- `release_gate_report.md` (human-readable summary)
- `release_gate_summary.json` (machine-readable summary)

`release_gate_summary.json` includes:

- `status` (`PASS` or `FAIL`)
- `checks` (list of named check results)
- `file_count_hashed`
- `missing_files`
- `mismatched_hashes`
- `signature` (mode/status/detail)

## E) Failure policy

Any failed MUST check results in overall `FAIL`.
A `FAIL` result means **do not ship**.

## F) Future hook

Signing verification support is defined in `docs/signing_policy.md`.
The gate supports optional detached-signature validation and can be elevated to required mode.
