# Proof Bundle Standard v1

- Status: DRAFT
- Version: 1.0
- Date: 2026-02-22

## 1. Purpose

This standard defines a minimal, vendor-neutral evidence bundle for deterministic replay claims. Any published claim SHOULD include a bundle conforming to this standard.

## 2. Required bundle contents

A proof bundle MUST include the following structure:

```text
<bundle_root>/
  manifest.json
  SHA256SUMS.txt
  environment/
    platform_fingerprint.json
    tool_versions.json
  inputs/
    input_payload.*
    options.*
    bytecode_or_rule_artifact.*
  outputs/
    decision_output.bin
    decision_record.json
```

Rules:

- `manifest.json` MUST declare schema version and list required artifacts.
- `SHA256SUMS.txt` MUST include all regular files except itself.
- `environment/*` is informational and MUST NOT be used as equality input unless explicitly declared.

## 3. Hash rules

- SHA-256 MUST be used for all artifact digests.
- Hash manifest paths MUST be repo/bundle-relative and use `/` separators.
- Entries in `SHA256SUMS.txt` MUST be sorted lexicographically by relative path.
- Hash computation MUST use canonical file bytes (stable newline policy per producing contract).

## 4. Determinism and timestamp policy

- Deterministic equality surfaces MUST exclude wall-clock capture fields.
- Timestamps are PROHIBITED in equality artifacts, except explicit injected test time fields (for example `now_utc_ms`) captured as inputs/options.
- Producers SHALL NOT inject ambient timezone or locale into equality fields.

## 5. Redaction and leakage rules

Bundle artifacts MUST NOT include host-identifying leakage in deterministic surfaces:

- Absolute paths (`C:\`, `/Users/`, `/home/`), usernames, hostnames, local profile paths.
- Machine identifiers, process IDs, ephemeral runner IDs.
- Locale-formatted numeric strings when canonical numeric format is required.

If such fields are needed for debugging, they SHOULD be isolated as non-equality informational metadata and explicitly marked.

## 6. Verification model (conceptual)

A verifier SHOULD perform these checks in order:

1. Validate manifest/schema version and required-file presence.
2. Recompute and compare `SHA256SUMS.txt` entries.
3. Validate decision record schema and equality fields.
4. Confirm deterministic equality claim (input/options/decision hashes as applicable).

Verification output SHOULD be concise, stable, and machine-readable.

## 7. Compatibility

- Minor revisions to this standard SHOULD be additive-only.
- Breaking layout or semantic changes MUST use a major version increment.
