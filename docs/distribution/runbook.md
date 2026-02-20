# Distribution Runbook

## Vendor flow (bundle build)

1. Build release binaries for engine and `ruledslc`.
2. Run bundle assembly:

```powershell
pwsh Tools/release_bundle/build_bundle.ps1 \
  -EngineBin <engine-binary> \
  -CompilerBin <ruledslc-binary> \
  -EngineImportLib <optional-import-lib> \
  -BundleType <Evaluation|Commercial> \
  -Out <bundle-dir>
```

3. Audit the assembled bundle:

```powershell
pwsh Tools/release_bundle/audit_bundle_layout.ps1 -BundleDir <bundle-dir>
```

4. Publish the bundle with `manifests/HASHES.txt` as the authoritative hash record.

## Customer flow (verify then integrate)

1. Verify delivery hashes using `manifests/HASHES.txt`.
2. Confirm compiler identity via `ruledslc --version`.
3. Compile rules:

```text
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3
```

4. Verify bytecode:

```text
ruledslc verify rules.axbc
```

5. Evaluate through C API only after compatibility check:

- `ax_check_bytecode_compatibility(...)`
- then `ax_eval_bytecode(...)` (or equivalent evaluation entrypoint)

## If hash verification fails

- Stop immediately.
- Do not execute binaries from the bundle.
- Request a fresh distribution package.
- Provide vendor support with the mismatched path and computed hash.

## Compatibility matrix usage

- Use `docs/compatibility_matrix.md` as the source of truth for compiler/language/AXBC/ABI alignment.
- Treat unmatched versions as incompatible until a new matrix is published.

## Release Gate

- `verify` CI status check MUST be green on the candidate commit.
- `Tools/release_bundle/audit_bundle_layout.ps1` MUST pass on the final bundle.
- `manifests/MANIFEST.json` and `manifests/HASHES.txt` MUST be generated and included.
- The release-candidate packet (RC bundle + hashes) MUST be archived before announcement.
- Publish/announce only after all gate items above pass.
## References

- `docs/distribution/bundle_standard.md`
- `docs/distribution/customer_verification.md`
- `docs/compatibility_matrix.md`
## Release checklist (minimal)

Before pushing a final tag (e.g., v1.0.0):

- Governance: PR-only + squash-only + required status check `verify` (strict) is active (see `docs/evidence/governance_snapshot_*.json`).
- Deterministic bundle: `MANIFEST.json` and `HASHES.txt` are byte-identical across two local bundle builds from the same commit.
- CI release validation: `audit-summary` artifact is produced and contains asset SHA256 for the release set.
  - Validated on tag `v1.0.0-rc.2`, run `22234987419` (success), commit `3aef8e5c2740c0f3e2de0029c3a4d107cdf3d8aa`.
