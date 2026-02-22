# Release Model Governance

- Status: DRAFT
- Version: 1.0
- Date: 2026-02-22

## 1. Purpose

This document defines release lanes and metadata rules for RuleDSL. Release metadata MUST remain consistent with governance and determinism contracts.

## 2. Release definitions

- **Phase marker**: architectural milestone tag (for example `governance-spine-v1`).
- **Proofing release**: governance/tooling validation release (for example `v1.0.1-proofing`).
- **Release candidate (rc)**: stabilization candidate before stable release (for example `v1.1.0-rc.1`).
- **Stable release**: production semver release tag (for example `v1.1.0`).

## 3. Naming rules

Tag names MUST follow one of these formats:

- Stable: `vMAJOR.MINOR.PATCH`
- Proofing: `vMAJOR.MINOR.PATCH-proofing` or `vMAJOR.MINOR.PATCH-proofing.N`
- RC: `vMAJOR.MINOR.PATCH-rc.N`
- Phase marker: `<name>-spine-vN`

Tags outside these formats SHALL be treated as governance violations.

## 4. Prerelease policy

- Phase marker releases MUST be published as prerelease.
- Proofing releases MUST be published as prerelease.
- RC releases MUST be published as prerelease.
- Stable semver releases MUST be published as non-prerelease.

## 5. Latest designation policy

- Only stable semver releases MAY be marked as Latest.
- Proofing, rc, and phase marker releases SHALL NOT be Latest.
- Latest designation is a manual governance action and MUST be verified after release edits.

## 6. Examples

Valid examples:

- `v1.0.0` + prerelease=false + Latest allowed
- `v1.0.1-proofing` + prerelease=true + Latest forbidden
- `v1.1.0-rc.1` + prerelease=true + Latest forbidden
- `governance-spine-v1` + prerelease=true + Latest forbidden

Invalid examples:

- `v1.0.1-proofing` + prerelease=false
- `governance-spine-v1` + prerelease=false
- non-semver release marked as Latest

## 7. Enforcement

Governance is enforced by:

- `.github/workflows/release-guard.yml`
- `Tools/release_guard/check_release_guard.py`

These checks SHALL fail on naming and prerelease policy violations.
