# Proof Bundle Template (v1)

This folder defines a minimal skeleton for deterministic evidence packaging.

## Intended use

- Copy this structure to a new proof bundle directory.
- Populate required artifacts from your deterministic run.
- Recompute `SHA256SUMS.txt` after all files are final.

## Minimal layout

```text
proof_bundle_template/
  manifest.json
  SHA256SUMS.txt
  environment/
    platform_fingerprint.json
    tool_versions.json
  inputs/
    input_payload.json
    options.json
    artifact.bin
  outputs/
    decision_output.bin
    decision_record.json
```

See `docs/governance/proof_bundle_standard_v1.md` for normative rules.
