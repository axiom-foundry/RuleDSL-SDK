# ADR-0003: Replay and evidence schema

## Status

Accepted

## Context

Replay evidence is used to prove deterministic equivalence. Schema drift, ambiguous optional fields, or inconsistent serialization rules can invalidate audit conclusions.

## Decision

Replay/evidence schema evolution follows strict version and serialization rules.

- Every record MUST include `schema_version`.
- Minor schema revisions in v1.x SHALL be additive-only.
- Breaking schema changes MUST use a new major schema version.
- Optional absent fields MUST use a single omission policy.
- Producers SHALL NOT alternate between omitted and `null` for the same semantic absence.

## Consequences

- Verifiers can apply stable compatibility logic.
- Evidence comparisons stay predictable across additive changes.
- Audit reviewers can interpret absence semantics consistently.
- Schema changes require explicit governance review.
