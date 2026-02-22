# Replay / Evidence Contract v1

- Status: DRAFT
- Version: 1.0
- Date: 2026-02-22
- Scope: replay evidence records and verification surface

## 1. Purpose

This contract defines the minimum replay/evidence surface required to make deterministic comparison claims. Evidence claims MUST be backed by artifacts that conform to this contract.

## 2. Evidence bundle minimum contents

A replay evidence bundle SHOULD include at minimum:

- `bytecode/`
  - bytecode artifact used for evaluation
  - bytecode SHA-256 sidecar
- `records/`
  - decision records (`replay_proof_v1` schema)
- `reports/`
  - verifier output report(s)
- `README.txt`
  - run context, commit references, command log
- archive output (`*.zip`) for transport/integrity workflows

Each bundle MUST be self-describing enough to re-run verification without private context.

## 3. Schema versioning and compatibility

Schema version rules:

- `schema_version` MUST be explicit in every record.
- Minor evolution in v1.x SHALL be additive-only.
- Existing field meaning MUST NOT change in v1.x.
- Breaking schema changes REQUIRE a major schema version bump.
- Verifiers SHOULD support known older minor variants where feasible.

## 4. Canonicalization rules

Canonicalization is mandatory for deterministic comparison surfaces:

- Key ordering MUST be stable and deterministic.
- Numeric formatting MUST be stable and locale-independent.
- Floating formatting SHOULD use a fixed canonical strategy defined by producer contract.
- Text encoding MUST be UTF-8.
- Field serialization SHALL NOT depend on machine locale or timezone.
- Paths/usernames/machine-specific absolute locations MUST NOT enter equality fields.

## 5. Omit vs null policy

This contract chooses OMIT policy for absent optional fields:

- If a field is not semantically available, producers MUST omit the field.
- Producers SHALL NOT switch between omit and explicit `null` for the same absence condition.
- Verifiers SHOULD treat policy violations as invalid evidence in strict mode.

For example, when outcome is non-OK and no decision payload exists, `decision_hash` MUST be omitted (not null).

## 6. Forbidden fields in equality surface

The following MUST NOT participate in deterministic equality claims:

- Wall-clock timestamps (except explicitly injected `now_utc_ms` captured as input/options evidence).
- Random seeds unless fixed and explicitly recorded.
- Machine identifiers (hostname, username, local profile paths, hardware IDs).
- Build-agent transient paths and process IDs.

Informational fields MAY exist, but strict equality surfaces SHALL remain free from ambient-environment leakage.

## 7. Verification policy summary

- Production/audit verification MUST run in strict mode.
- Equality claims SHALL require matching contract fields per active schema/version policy.
- Evidence with missing required strict fields MUST be treated as invalid.

This contract is normative for replay/evidence governance in v1.x.
