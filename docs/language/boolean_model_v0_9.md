# RuleDSL v0.9 Boolean and Equality Model Annex

This annex defines boolean-domain, condition-context, and equality semantics for v0.9.

## 1) Boolean Type Contract

- [TYP-0005] The language Boolean value domain SHALL contain exactly two values: `true` and `false`.

## 2) Condition-context Rules

- [SEM-0017] Condition-context evaluation SHALL accept only Boolean results.

## 3) Truthiness and Coercion Policy

- [TYP-0006] Implicit truthiness coercion from non-Boolean types to Boolean SHALL be forbidden.
- [ERR-0013] If condition-context evaluation receives a non-Boolean value at runtime, evaluation SHALL raise `ERR.RUNTIME.CONDITION_TYPE`; classification is runtime error and identifier meaning SHALL remain stable across compatible versions.

## 4) Equality and Inequality Semantics

- [SEM-0018] Equality and inequality operations SHALL be defined only for operands of the same language type.
- [ERR-0014] If cross-type equality or inequality reaches runtime evaluation, evaluation SHALL raise `ERR.RUNTIME.EQUALITY_TYPE_MISMATCH`; classification is runtime error and identifier meaning SHALL remain stable across compatible versions.
- [SEM-0019] String equality SHALL be byte-exact over UTF-8 octet sequences.
- [SEM-0020] Missing equality semantics SHALL be: `missing == missing` is `true`; `missing != missing` is `false`; `missing == <non-missing>` is `false`; `missing != <non-missing>` is `true`.

## 5) Determinism Notes for String Comparison

- [DET-0018] String equality evaluation SHALL be locale-independent and collation-independent.

## 6) Runtime Error Taxonomy

- [ERR-0015] Boolean/equality runtime error identifiers SHALL use the `ERR.RUNTIME.<TOKEN>` namespace and SHALL preserve identifier meaning across compatible versions.

Taxonomy entries:

- `ERR.RUNTIME.CONDITION_TYPE`
  - Trigger: a condition-context expression produces a non-Boolean value.
  - Classification: runtime error.
  - Stability: symbolic identifier meaning is stable across compatible versions.
- `ERR.RUNTIME.EQUALITY_TYPE_MISMATCH`
  - Trigger: cross-type equality/inequality reaches runtime evaluation.
  - Classification: runtime error.
  - Stability: symbolic identifier meaning is stable across compatible versions.
