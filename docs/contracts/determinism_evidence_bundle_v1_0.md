# Determinism Evidence Bundle (v1.0)

This document defines the minimum evidence bundle required to support RuleDSL 1.0 determinism conformance claims.

## 1. Normative scope

- This standard applies to determinism evidence under `reports/determinism_v1_0/`.
- Published conformance claims for `DET-*` requirements MUST include an evidence bundle that follows this document.
- Evidence bundles SHOULD be generated per platform/configuration run and archived without post-generation mutation.

## 2. Required directory layout

Evidence bundles MUST use this minimum structure:

```text
reports/determinism_v1_0/<date>/<platform>/<config>/
  manifest.json
  SHA256SUMS.txt
  inputs/
  outputs/
  environment/
```

Layout requirements:

- `<date>` MUST use `YYYY-MM-DD`.
- `<platform>` MUST identify supported platform variants (for example `windows-x64` or `linux-x64`).
- `<config>` MUST identify deterministic run configuration (for example `release-strict`).
- `inputs/` MUST include bytecode hash evidence and canonical input artifacts.
- `outputs/` MUST include output payload files mapped to requirement IDs.
- `environment/` MUST include platform fingerprint and tool-version evidence used for the run.

## 3. Required files and content

- `manifest.json` MUST exist and MUST conform to the schema in Section 4.
- `SHA256SUMS.txt` MUST contain SHA-256 checksums for all files in the bundle except itself.
- `inputs/` MUST contain:
  - Bytecode hash record (`bytecode.sha256` or equivalent deterministic JSON form).
  - Canonical input artifact(s) used for evaluation replay.
- `outputs/` MUST contain at least one requirement-mapped file per claimed `DET-*`.
- `environment/` MUST contain:
  - Platform fingerprint file.
  - Tool/runtime version file.
- `environment/platform_fingerprint.json` is informational and is not part of cross-platform bit-identical output equality claims.

## 4. Minimal `manifest.json` schema

`manifest.json` MUST be UTF-8 JSON with these required top-level keys:

- `schema_version` (string, fixed value `determinism-evidence-bundle-v1.0`)
- `contract_version` (string, fixed value `determinism-contract-v1.0`)
- `date` (string, `YYYY-MM-DD`)
- `platform` (string)
- `config` (string)
- `bytecode_sha256` (string, 64 lowercase hex chars)
- `canonical_input_artifacts` (array of relative paths)
- `requirements` (array of objects)

Each item in `requirements` MUST include:

- `id` (string, `DET-xxx`)
- `test` (string)
- `output_file` (relative path under `outputs/`)
- `status` (string, for example `pass` or `fail`)

## 5. Requirement-to-file naming

- Evidence file names under `outputs/` MUST start with requirement ID prefix.
- Required pattern: `DET-xxx_<descriptor>.json`.
- Example: `DET-001_smoke.json`.
- The `requirements[].output_file` field in `manifest.json` MUST match the actual file name exactly.

## 6. Bit-identical output comparison

- Bit-identical output comparisons MUST include:
  - Public API status code value.
  - Output buffer bytes produced by evaluation for the compared case.
- If an error path is under test, error code bytes and error detail buffer bytes SHOULD be captured in the mapped output artifact.

## 7. Conformance publication rule

- A determinism conformance claim MUST NOT be published without a complete evidence bundle.
- If evidence is incomplete, the claim status MUST be treated as unverified.
