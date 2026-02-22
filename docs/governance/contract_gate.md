# Contract Gate

- Status: DRAFT
- Version: 1.0
- Date: 2026-02-22

## Purpose

The contract gate enforces explicit acknowledgement when a pull request touches frozen governance or compatibility surfaces.

## Frozen surfaces

The following paths are treated as contract-critical:

- `include/**`
- `docs/architecture/**`
- `docs/language/**`
- `docs/bytecode_workflow_*`
- `docs/governance/**`

## Required PR declaration

If any frozen surface file changes, the PR body MUST contain the exact line:

`Contract change: YES`

If frozen surfaces change and this line is missing, the `contract-gate` workflow SHALL fail.

## Policy intent

This gate forces reviewer visibility for contract-impacting changes and reduces silent drift across ABI, determinism, replay/evidence, and governance surfaces.

## Normative alignment

This gate SHOULD be interpreted with:

- `docs/architecture/architectural_freeze_charter_v1_0.md`
- `docs/architecture/c_api_abi_evolution_contract_v1.md`
- `docs/architecture/replay_evidence_contract_v1.md`
