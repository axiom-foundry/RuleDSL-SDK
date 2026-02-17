# RuleDSL Language v0.9 - Contract Status Snapshot

## 1. Scope
- Active profile: `decision-rules-v0.9`
- Language version: `v0.9`
- Engine implementation: private
- Language specification: versioned and normative

## 2. Grammar & Surface Policy
- Identifiers are ASCII-only.
- Keyword matching is ASCII case-insensitive.
- Logical operators are keyword-only: `and`, `or`, `not`.
- Numeric exponent literals (`e`/`E`) are OUT-OF-CONTRACT in v0.9.
- Implicit coercions are not allowed.
- Operator precedence is deterministic and fixed by the v0.9 grammar table.

## 3. Determinism Guarantees
- Lexical classification is locale-independent and ASCII-explicit.
- Numeric behavior follows an IEEE 754 binary64 model.
- Non-finite numeric values are rejected by contract.
- Fast-math style behavior drift is out-of-contract.
- Identifier lookup/equality uses UTF-8 octet matching with no Unicode normalization.

## 4. Conformance Infrastructure
- Conformance targets:
  - `axiom_ruledsl_logical_ops_conformance_tests`
  - `axiom_ruledsl_keyword_case_conformance_tests`
  - `axiom_ruledsl_identifier_class_conformance_tests`
  - `axiom_ruledsl_numeric_literal_conformance_tests`
- STRICT mode is enabled with `RULEDSL_CONFORMANCE_STRICT=1`.
- Reports are emitted to `reports/lang_conformance/*.json`.
- Windows and Linux strict CI validation exists.
- Strict CI validation is currently informational (non-blocking).

## 5. Enforcement Model
- OBSERVE mode (default): tests collect evidence and emit JSON reports.
- STRICT mode: tests enforce locked v0.9 contract decisions and fail on drift.
- CI uploads conformance JSON reports as artifacts for review and traceability.
