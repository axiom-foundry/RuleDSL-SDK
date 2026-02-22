# Public Surface Inventory

- Status: DRAFT
- Version: 1.0
- Date: 2026-02-22

## What is public surface

For manifest drift control, public surface is the committed header tree under `include/**`.

This surface is contract-critical and MUST remain synchronized with:

- `docs/architecture/c_api_abi_evolution_contract_v1.md`
- `docs/architecture/architectural_freeze_charter_v1_0.md`
- `docs/governance/contract_change_policy.md` (when applicable)

## Contract declaration rule

Any pull request that changes the public surface MUST declare in PR body:

`Contract change: YES`

This requirement aligns with the contract gate workflow for frozen surfaces.

## Manifest file

- Manifest path: `docs/governance/public_surface_manifest.sha256`
- Format: `SHA256<two spaces><repo-relative-path>`
- Ordering: stable lexical order by repo-relative path
- Timestamps: forbidden in manifest output

## How to regenerate manifest

Run from repository root:

```powershell
python Tools/public_surface_hash/gen_manifest.py
```

To check for drift without rewriting:

```powershell
python Tools/public_surface_hash/gen_manifest.py --check
```

If check fails, regenerate manifest, commit the updated file, and ensure PR body includes `Contract change: YES` when contract-critical surface changed.
