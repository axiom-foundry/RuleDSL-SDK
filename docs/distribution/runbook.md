# Distribution Runbook

## Vendor flow (bundle build)

1. Build release binaries for engine and `ruledslc`.
2. Run bundle assembly:

```powershell
pwsh Tools/release_bundle/build_bundle.ps1 `
  -EngineBin <engine-binary> `
  -CompilerBin <ruledslc-binary> `
  -EngineImportLib <optional-import-lib> `
  -BundleType <Evaluation|Commercial> `
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

## PyPI 1.2.0 operator flow

The release rule is **build once, publish the same bytes**. Never rebuild after
TestPyPI: the wheel and sdist uploaded to production PyPI must come from the
same immutable GitHub Actions artifact.

1. On `main`, manually run `pypi-rc-build.yml`. It performs the only release
   build, verifies package metadata and smoke checks, and logs the RC workflow
   run ID plus artifact ID. Preserve both IDs.
2. Run `pypi-publish.yml` with `target=testpypi` and those RC IDs. The fixed
   GitHub environment is `testpypi`. After upload, the separate
   `verify-testpypi-registry` job (which has no OIDC token permission) queries
   the TestPyPI 1.2.0 JSON endpoint with bounded retries. It requires exactly
   the expected wheel and sdist, compares TestPyPI's SHA-256 values with
   `RC_METADATA.json`, downloads and fully hashes both files, and installs the
   downloaded wheel in a clean virtual environment for `pip check`, imports,
   MCP 0.2.0, and console `--help` smoke checks. Only then does the job upload
   `TESTPYPI_VERIFICATION.json`. Preserve this successful workflow run ID.
   If registry propagation is delayed, rerun only the failed verification job;
   the already-successful TestPyPI upload job does not need to run again.
3. Run `pypi-publish.yml` with `target=pypi`, the **same** RC IDs, the successful
   TestPyPI publish run ID, and confirmation `publish-ruledsl-1.2.0`. The fixed
   GitHub environment is `pypi` and must require an authorized reviewer before
   its OIDC publish job may start.

Both publish paths download by exact artifact ID and reject a failed/wrong
workflow run, non-`main` source, repository mismatch, expired artifact, wrong
source commit or Git tree, version/metadata drift, extra files, unsafe ZIP
paths, and any wheel/sdist SHA-256 mismatch. The publisher receives only the
workspace-relative `pypi-publish-dist` directory, which must not preexist and
is populated with exactly the rehashed wheel and sdist. Production also
requires the exact run-attempt-bound post-registry receipt and rejects an
upload-time copy of `RC_METADATA.json` as insufficient evidence.

Trusted Publishing configuration lives outside this repository and cannot be
verified by these files. The expected TestPyPI pending-publisher identity is:

- owner: `axiom-foundry`
- repository: `RuleDSL-SDK`
- workflow: `pypi-publish.yml`
- environment: `testpypi`

Before using the production path, repository administrators must separately
confirm that the `pypi` environment is protected (required reviewers and only
the intended `main` deployment branch) and that the existing production PyPI
Trusted Publisher names `pypi-publish.yml` with environment `pypi`. This change
does not create or alter either environment or any PyPI/TestPyPI publisher.

## References

- `docs/distribution/bundle_standard.md`
- `docs/distribution/customer_verification.md`
- `docs/compatibility_matrix.md`
## Release checklist (minimal)

Before pushing a final tag (e.g., v1.0.0):

- Governance: PR-only + squash-only + required status check `verify` (strict) is active (see `docs/evidence/governance_snapshot_*.json`).
- Deterministic bundle: `MANIFEST.json` and `HASHES.txt` are byte-identical across two local bundle builds from the same commit.
- CI release validation: the `bundle-linux` workflow produces the release artifact set (`<prefix>.tar.gz`, `<prefix>.zip`, `SHA256SUMS.txt`) and `audit_bundle_layout.ps1` passes on the assembled bundle.
