# RuleDSL v0.9 Identifier and Missing Semantics Annex

This annex defines identifier resolution and missing-value behavior for v0.9.

## 1) Identifier Role

- [TYP-0007] `identifier` SHALL denote a symbolic reference form that requires deterministic resolution before value-consuming operations.

## 2) Name Resolution Semantics

- [SEM-0024] Identifier lookup SHALL resolve against caller-provided input scope using deterministic key matching.
- [SEM-0025] Identifier lookup SHALL be case-sensitive, SHALL use exact UTF-8 octet key matching, and SHALL NOT apply Unicode normalization.

## 3) Missing Origins and Domain Behavior

- [SEM-0026] If deterministic lookup cannot find a referenced key/path in the provided input scope, evaluation SHALL yield `missing` and SHALL NOT raise a direct runtime error at lookup time.
- [TYP-0008] `missing` SHALL be a distinct language value and SHALL NOT be implicitly converted to number, string, or boolean.

## 4) Operation Constraints for `missing` and `identifier`

Condition-context rules are defined by `docs/language/boolean_model_v0_9.md`.
Ordering rules are defined by `docs/language/ordering_model_v0_9.md`.

- [SEM-0027] Value-consuming operations SHALL require resolved concrete operands; unresolved `identifier` operands are not valid operation inputs.
- [ERR-0020] If an operation requiring a concrete operand receives `missing`, evaluation SHALL raise `ERR.RUNTIME.MISSING_OPERAND`; classification is runtime error and identifier meaning SHALL remain stable across compatible versions.

## 5) Determinism Constraints for Lookup and Missing

- [DET-0020] Identifier resolution and missing detection SHALL be locale-independent and collation-independent.
- [DET-0021] Identifier resolution SHALL be independent of host map iteration order and platform-specific dictionary behavior.
- [DET-0022] Identifier lookup and string equality SHALL operate on raw UTF-8 octet sequences without Unicode normalization (NFC/NFD/etc.).

## 6) Runtime Error Taxonomy

- [ERR-0019] Identifier/missing runtime error identifiers SHALL use the `ERR.RUNTIME.<TOKEN>` namespace and SHALL preserve identifier meaning across compatible versions.
- [ERR-0022] `ERR.RUNTIME.UNRESOLVED_IDENTIFIER` SHALL be treated as deprecated in v0.9 and SHALL NOT be emitted by compliant evaluators.

Taxonomy entries:

- `ERR.RUNTIME.MISSING_OPERAND`
  - Trigger: operation requiring concrete operand receives `missing`.
  - Classification: runtime error.
  - Stability: symbolic identifier meaning is stable across compatible versions.

Deprecated identifier (not emitted in v0.9):

- `ERR.RUNTIME.UNRESOLVED_IDENTIFIER`
