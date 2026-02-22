# Architectural Freeze Charter v1.0

- Status: DRAFT
- Version: 1.0
- Date: 2026-02-22
- Audience: maintainers, release approvers, integrators

## 1. Purpose

This charter defines the architectural surfaces that are frozen for RuleDSL v1.x. Any change that touches a frozen surface MUST be reviewed as a contract change before merge.

## 2. Scope & boundaries (Public SDK vs Private Engine/Compiler)

RuleDSL operates across two boundaries:

- Public SDK boundary (this repository): public headers, public docs, replay/evidence tooling contracts, and release governance metadata.
- Private Engine/Compiler boundary (outside this repository): engine implementation, compiler internals, private build pipelines, and private operational controls.

Public claims SHALL be made only from the public SDK boundary. Private implementation details SHALL NOT be treated as public contract unless explicitly published in public docs.

## 3. Frozen surfaces

The following surfaces are frozen for v1.x:

- Language spec versioning and compatibility
  - Published language profiles and compatibility statements MUST remain stable within v1.x.
  - Clarifications MAY be added, but existing normative meaning SHALL NOT be redefined.
- Public C API/ABI stability guarantees
  - Public ABI behavior MUST follow `docs/architecture/c_api_abi_evolution_contract_v1.md`.
  - Existing ABI-visible semantics SHALL NOT be broken in v1.x.
- Determinism contract (time injection, locale, floating rules)
  - Determinism claims MUST use explicit inputs, injected time, and locale-independent processing.
  - Floating behavior SHALL remain aligned with published numeric rules.
- Replay/Evidence contract (schema versioning, canonicalization)
  - Evidence record/schema behavior MUST follow `docs/architecture/replay_evidence_contract_v1.md`.
  - Equality surfaces and canonicalization rules SHALL remain stable in v1.x.
- Release/Tag governance (phase markers vs latest)
  - Stable releases, proofing releases, and phase markers MUST remain distinct lanes.
  - Phase markers and proofing tags SHALL NOT be represented as stable product increments.

## 4. Change control policy

### 4.1 Forbidden in v1.x

The following are forbidden in v1.x:

- Silent determinism drift under identical contract inputs.
- Reassignment of existing stable error code meaning.
- Backward-incompatible ABI contract changes.
- Undocumented equality-surface changes in replay verification.

### 4.2 Requires v2 (major bump)

A major version bump (v2+) is REQUIRED for:

- Any incompatible public ABI/C API change.
- Any breaking replay/evidence schema change.
- Any change that invalidates existing determinism preconditions or equality fields.

### 4.3 Safe additive change (v1.x)

The following MAY be added in v1.x when non-breaking and documented:

- New optional fields with defined defaults and no semantic break.
- New additive enum members with unknown-value handling preserved.
- Clarifying normative text that does not alter prior requirements.

All additive changes SHOULD include tests and migration notes where applicable.

## 5. Non-goals / WILL NOT BUILD

The project WILL NOT BUILD the following as part of v1.x public scope:

- Hosted SaaS or managed control-plane features.
- Public open-source release of private engine/compiler implementation.
- Non-deterministic feature surfaces relying on ambient system time, locale, or random behavior without fixed injection.
- Network/distributed-consensus guarantees as part of core RuleDSL determinism contract.

## 6. Enforcement (CI, branch protection, PR-only, verify required)

Governance enforcement rules:

- Protected branches MUST require pull request review and required checks.
- Direct pushes to protected branches SHALL be disallowed.
- The required `verify` check MUST pass before merge.
- Contract-impacting doc changes SHOULD be reviewed against RFC-001/RFC-002 and replay/evidence contracts.

This charter is normative for v1.x architectural governance.
