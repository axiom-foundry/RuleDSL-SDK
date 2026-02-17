# RuleDSL Language Specification v0.9 (Draft)

## 1) Scope and Non-goals

This document defines the normative language baseline for v0.9 under freeze governance.

- [VER-0002] v0.9 SHALL introduce no new language features, operators, or implicit runtime dependencies beyond the freeze baseline.
- [VER-0006] Clarifications and defect corrections SHALL preserve observable language behavior for previously valid programs.

## 2) Normative Keywords

The keywords `MUST`, `SHALL`, and `MAY` are interpreted as normative requirement markers.

- [SYN-0001] Normative requirements in this specification SHALL use exactly one primary requirement ID in square brackets.

## 3) Language Model Overview

RuleDSL evaluates compiled programs against caller-provided inputs and options.

The v0.9 baseline profile is defined by `docs/language/profile_decision_rules_v0_9.md`.

String literal source encoding, delimiters, and escape decoding are defined by `docs/language/string_lexing_v0_9.md`.

Whitespace/comments, identifier+keyword tokenization, and numeric-literal lexical forms are defined by `docs/language/lexical_core_v0_9.md`.

- [SEM-0001] Program evaluation SHALL be a pure function of language version, bytecode artifact, explicit inputs, and explicit options.
- [SEM-0002] Evaluation SHALL yield either a defined decision result or a defined error outcome.

## 4) Evaluation Semantics

This section locks core execution semantics.

- [SEM-0003] Expression evaluation order SHALL be left-to-right by source structure unless an explicitly specified construct defines a different order.
- [SEM-0004] Conditional evaluation SHALL short-circuit and SHALL NOT evaluate non-selected branches.
- [SEM-0005] Evaluation SHALL NOT mutate host or process state outside the evaluator-owned result container.
- [SEM-0006] Observable side effects SHALL be limited to explicit API-mediated diagnostics configured by the caller.

## 5) Type System

This section defines the high-level typing contract.

Boolean type-domain, condition-context, truthiness, and equality semantics are defined by `docs/language/boolean_model_v0_9.md`.

Ordering semantics for `<`, `>`, `<=`, and `>=` are defined by `docs/language/ordering_model_v0_9.md`.

Identifier resolution and missing-value semantics are defined by `docs/language/identifier_missing_v0_9.md`.

- [TYP-0001] Values SHALL belong to the public language type categories: number, string, identifier, boolean, and missing.
- [TYP-0002] Implicit coercion SHALL be forbidden unless a normative clause explicitly defines it.
- [TYP-0003] Statically detectable type violations SHALL fail at compile time.
- [TYP-0004] Ambiguous type resolution SHALL fail at compile time.

## 6) Numeric Model

This section binds numeric semantics to a concrete annex.

Numeric error taxonomy and compile-time constant-folding constraints are defined by the annex.

- [SEM-0007] Numeric semantics SHALL conform to `docs/language/numeric_model_v0_9.md`.
- [SEM-0008] Handling of non-finite values, overflow, underflow, and subnormal values SHALL follow the annex.
- [DET-0010] Determinism-critical arithmetic environment constraints SHALL follow the annex.

## 7) Error Model

This section binds compile/runtime responsibility.

- [ERR-0005] Syntax, typing, and static semantic violations SHALL fail at compile time and SHALL NOT defer to runtime.
- [ERR-0006] Runtime failures SHALL preserve stable public error-code semantics across compatible versions.
- [ERR-0007] Diagnostic text MAY vary, but runtime classification and code meaning SHALL remain stable.

## 8) Determinism Constraints

This section summarizes required deterministic boundaries.

- [DET-0011] Evaluation SHALL NOT read wall-clock time, timezone, locale, environment variables, or filesystem enumeration state unless explicitly provided as input.
- [DET-0012] Evaluation SHALL NOT depend on randomness, memory addresses, or nondeterministic iteration artifacts.
- [DET-0013] Equivalent executions with identical language version, bytecode, inputs, and options SHALL produce identical observable outcomes.

## 9) Bytecode + Versioning Policy

This section binds language behavior to artifact/version compatibility.

- [BC-0001] Bytecode artifacts SHALL expose schema/version metadata sufficient for deterministic compatibility validation.
- [BC-0002] Runtime SHALL reject bytecode outside the supported compatibility window with a defined error outcome.
- [VER-0001] v0.9 semantics SHALL remain compatible with the planned v1.0 baseline contract.
- [VER-0003] A breaking change SHALL include any parse, type, semantic, determinism, or public error-code compatibility break for previously valid programs.

## 10) Conformance Mapping Guidance

Conformance evidence binds requirements to executable tests.

- [VER-0004] Each normative requirement ID SHALL map to at least one conformance test entry in `docs/language/conformance_map.md`.
- [VER-0005] A specification change that adds or changes a normative clause SHALL update its conformance mapping in the same change.
