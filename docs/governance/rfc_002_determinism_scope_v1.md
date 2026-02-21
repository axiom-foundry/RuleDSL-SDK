# RFC-002: Determinism Scope v1

- Status: DRAFT
- Date: 2026-02-21
- Depends on: RFC-001 (`docs/governance/rfc_001_system_boundary_v1.md`)

## 1. Purpose

This RFC defines exactly what "deterministic" means for RuleDSL decision evaluation and evidence comparison, and what remains outside that guarantee boundary.

## 2. Determinism Definition (Normative)

**[RFC002-REQ-001]** Determinism claims SHALL be evaluated only when the following inputs are identical: `engine_version_string`, `abi_level`, `bytecode_hash`, canonical input bytes (`input_hash`), and evaluation options.

**[RFC002-REQ-002]** Under the preconditions in [RFC002-REQ-001], the engine SHALL produce an identical `decision_hash`.

**[RFC002-REQ-003]** Under the preconditions in [RFC002-REQ-001], the engine SHALL produce an identical `error_code` when an error is emitted.

**[RFC002-REQ-004]** Under the preconditions in [RFC002-REQ-001], the engine SHALL produce an identical structural validation outcome.

**[RFC002-REQ-005]** If any input listed in [RFC002-REQ-001] differs, determinism guarantees SHALL be treated as void for that comparison.

## 3. Deterministic Surfaces

| Surface | Deterministic? | Scope | Evidence Hook |
|---|---|---|---|
| Expression evaluation order | YES | Rule expression execution under fixed bytecode/input/options | `decision_hash`, trace conformance tests |
| Boolean short-circuit behavior | YES | Logical operator evaluation order and stop conditions | `decision_hash`, conformance tests |
| Numeric model (IEEE-754 binary64, ties-to-even) | CONDITIONAL | Deterministic when numeric contract in Section 4 is respected | `decision_hash`, numeric conformance tests |
| Error code emission | YES | Stable error code for identical invalid inputs | `error_code` |
| Bytecode validation result | YES | Structural/compatibility result for identical bytecode + ABI contract | validation status + `error_code` |
| Decision hash computation | YES | Hash over canonical decision output payload | `decision_hash` |
| JSON field ordering in `replay_proof_v1` | CONDITIONAL | Deterministic when producer follows schema/order contract | record byte content + verifier report |
| Wall-clock time | NO | Out of scope | none |
| Thread scheduling | NO | Out of scope | none |
| Memory allocation address layout | NO | Out of scope | none |
| File system state | NO | Out of scope | none |
| Network state | NO | Out of scope | none |

**[RFC002-REQ-006]** Surfaces marked NO in this section SHALL be treated as out of determinism scope.

## 4. Numeric Model Contract

**[RFC002-REQ-007]** Floating-point evaluation SHALL use IEEE-754 binary64 semantics.

**[RFC002-REQ-008]** Rounding mode SHALL be ties-to-even.

**[RFC002-REQ-009]** Fast-math style optimizations that alter numerical results are PROHIBITED.

**[RFC002-REQ-010]** Undefined behavior in numeric evaluation is PROHIBITED.

## 5. Error Determinism

**[RFC002-REQ-011]** For identical invalid inputs, identical `error_code` SHALL be emitted.

`error_message` text MAY vary and is informational unless explicitly declared as contractual in a versioned error surface.

## 6. Evidence Mapping

**[RFC002-REQ-012]** Equality proof for replay evidence MUST compare and match all of the following fields: `engine_version_string`, `abi_level`, `bytecode_hash`, `input_hash`, and `decision_hash`.

References:
- RFC-001: `docs/governance/rfc_001_system_boundary_v1.md`
- Audit answer template: `docs/governance/audit_answer_template_replay_proof_v1.md`
- Replay proof schema: `Tools/replay_proof/replay_proof_schema_v1.md`

## 7. Non-Goals

**[RFC002-REQ-013]** Determinism claims SHALL NOT be extended across different engine major versions.

**[RFC002-REQ-014]** Determinism claims SHALL NOT be extended across different ABI levels.

**[RFC002-REQ-015]** Determinism claims SHALL NOT be extended across builds using compiler flags that alter numeric behavior.

**[RFC002-REQ-016]** Determinism claims SHALL NOT be extended across hardware contexts when the numeric model contract is violated.

## 8. Stability Clause

**[RFC002-REQ-017]** Requirement IDs in RFC-002 SHALL remain stable across edits.

**[RFC002-REQ-018]** New normative requirements SHALL append new IDs, and existing IDs SHALL NOT be renumbered.
