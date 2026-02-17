# RuleDSL v0.9 Ordering and Comparison Model Annex

This annex defines ordering semantics for `<`, `>`, `<=`, and `>=` in v0.9.

## 1) Operand Type Rule

- [SEM-0021] Ordering operations SHALL be defined only when both operands have the same language type.
- [ERR-0016] If an ordering operation receives operands of different language types at runtime, evaluation SHALL raise `ERR.RUNTIME.ORDERING_TYPE_MISMATCH`; classification is runtime error and identifier meaning SHALL remain stable across compatible versions.

## 2) Numeric Ordering Semantics

`NaN` and infinities are handled by `docs/language/numeric_model_v0_9.md` and are not valid language-level numeric operands for ordering.

- [SEM-0022] Numeric ordering SHALL use IEEE 754 binary64 comparison semantics over finite values, and `-0.0` and `+0.0` SHALL compare as equal.

## 3) String Ordering Semantics

- [SEM-0023] String ordering SHALL be lexicographic over UTF-8 octet sequences.

## 4) Missing and Identifier Ordering Policy

- [ERR-0017] Any ordering operation involving `missing` or `identifier` operands SHALL raise `ERR.RUNTIME.ORDERING_INVALID_TYPE`; classification is runtime error and identifier meaning SHALL remain stable across compatible versions.

## 5) Determinism Constraints

- [DET-0019] Ordering evaluation SHALL be locale-independent, collation-independent, and free of platform-specific comparison behavior.

## 6) Runtime Error Taxonomy

- [ERR-0018] Ordering runtime error identifiers SHALL use the `ERR.RUNTIME.<TOKEN>` namespace and SHALL preserve identifier meaning across compatible versions.

Taxonomy entries:

- `ERR.RUNTIME.ORDERING_TYPE_MISMATCH`
  - Trigger: operands have different language types.
  - Classification: runtime error.
  - Stability: symbolic identifier meaning is stable across compatible versions.
- `ERR.RUNTIME.ORDERING_INVALID_TYPE`
  - Trigger: ordering uses `missing` or `identifier` operands.
  - Classification: runtime error.
  - Stability: symbolic identifier meaning is stable across compatible versions.
