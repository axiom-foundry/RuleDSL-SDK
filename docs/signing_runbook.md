# Signing Runbook

This runbook defines the operational workflow for detached signing of release hash manifests.
It complements `docs/signing_policy.md` and `docs/release_gate.md`.

## Workflow

### A) Build unsigned release package

Run release packager without signature input:

```powershell
python Tools/release_packager/release_packager.py --version <x.y.z> --out-root <out-root> --bin-dir <bin-dir> --include-dir <include-dir> --abi-level <abi-level> --bytecode-schema <schema> --os <os> --arch <arch>
```

Result includes `RuleDSL-<version>/SHA256SUMS.txt`.

### B) Sign SHA256SUMS.txt offline

Use signer with external private key file:

```powershell
python Tools/release_signer/release_signer.py --sha256sums <release-dir>/SHA256SUMS.txt --key-id <key-id> --private-key <secure-key-file.json> --out <release-dir>/SHA256SUMS.sig.json
```

### C) Verify with release gate

Verify signature and release integrity:

```powershell
python Tools/release_gate/release_gate.py --release-dir <release-dir> --out-dir <gate-report-dir> --sig-file <release-dir>/SHA256SUMS.sig.json --keyring docs/signing_keys.json
```

If signature is required for the distribution tier, run with `--require-signature`.

### D) Deliver release

Ship release folder only after gate result is PASS.

## Keyring publication/update

When activating a new signing key:

1. Add/replace entry in `docs/signing_keys.json` with active status.
2. Populate `public_key` with verifier format `n_hex:e_hex`.
3. Keep old key entry as `revoked` when rotating out.
4. Commit keyring updates before using the key in production release delivery.

## Criteria to flip to required signature

Move from optional to required signature only when all are true:

- `docs/signing_keys.json` contains active non-placeholder key material.
- At least N consecutive releases are signed and verified successfully.
- Revocation and rotation flow has been tested in staging.
- Support/oncall runbook includes signature-failure triage steps.

## References

- `docs/signing_policy.md`
- `docs/release_gate.md`
- `docs/distribution.md`