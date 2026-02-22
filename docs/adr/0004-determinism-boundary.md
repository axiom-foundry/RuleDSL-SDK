# ADR-0004: Determinism boundary

## Status

Accepted

## Context

Deterministic claims fail when outcomes depend on ambient process state such as wall clock, locale, random sources, or unstable ordering.

## Decision

RuleDSL determinism is bounded by explicit input and serialization controls.

- Time-dependent behavior MUST use injected values (for example `now_utc_ms`).
- Deterministic formatting and parsing MUST be locale-independent.
- Equality-critical output ordering MUST be stable and explicit.
- Randomness MUST NOT affect deterministic outputs unless a fixed seed is explicit evidence input.

## Consequences

- Determinism claims become testable and repeatable across environments.
- Hidden environment coupling is easier to detect in review.
- Replay bundles remain comparable in strict verification mode.
- Any boundary expansion requires explicit contract update.
