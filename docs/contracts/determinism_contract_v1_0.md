# Determinism Contract (v1.0)

RuleDSL 1.0 Determinism Guarantee: For identical bytecode, normalized input, and evaluation options on supported platforms, the SDK MUST produce bit-identical output.

## 1. Status and scope

- This RFC defines the RuleDSL 1.0 determinism contract for the public SDK evaluation boundary.
- This RFC applies to supported platforms only: Windows x64 and Linux x64.
- This RFC is normative for determinism behavior; implementation details are non-normative unless explicitly linked as evidence.

## 2. Definitions

- Identical bytecode: two bytecode inputs are identical only when their byte length and every byte value are equal.
- Normalized input: a caller-provided evaluation payload canonicalized per [`docs/contracts/input_canonicalization_v1_0.md`](input_canonicalization_v1_0.md), including deterministic field ordering, duplicate-key rejection, and locale-independent formatting rules.
- Evaluation options: explicit evaluation parameters that can alter behavior (for example policy flags); omitted options use documented defaults.
- Bit-identical output: API-visible outputs are equal byte-for-byte, including status codes, decision values, and any output buffers defined by the API contract.
- Supported platforms: Windows x64 and Linux x64 only.

## 3. Normative requirements

- [DET-001] Implementations MUST enforce deterministic evaluation for identical bytecode, normalized input, and evaluation options.
- [DET-002] Implementations MUST NOT use wall-clock time, timezone, locale, or randomness as implicit evaluation inputs.
- [DET-003] Implementations MUST treat bytecode as binary data and MUST NOT perform text decoding assumptions during evaluation.
- [DET-004] Callers MUST provide normalized input before invoking evaluation APIs.
- [DET-005] Implementations MUST define deterministic defaults for omitted evaluation options.
- [DET-006] Determinism claims MUST be interpreted only on supported platforms.
- [DET-007] Implementations SHOULD document any platform-specific constraints that affect deterministic execution.
- [DET-008] Implementations MUST NOT depend on filesystem enumeration order for evaluation behavior.
- [DET-009] Implementations MUST keep reserved option fields stable and ignored unless explicitly versioned.
- [DET-010] Any detected determinism violation SHOULD be reported through conformance evidence.

## 4. Relationship to companion documents

- Non-goals are defined in [`docs/contracts/determinism_non_goals_v1_0.md`](determinism_non_goals_v1_0.md).
- Strict undefined behavior boundaries are defined in [`docs/contracts/undefined_behavior_v1_0.md`](undefined_behavior_v1_0.md).
- Canonical input normalization rules are defined in [`docs/contracts/input_canonicalization_v1_0.md`](input_canonicalization_v1_0.md).
- Determinism evidence bundle requirements are defined in [`docs/contracts/determinism_evidence_bundle_v1_0.md`](determinism_evidence_bundle_v1_0.md).
- Requirement-to-evidence placeholders are defined in [`docs/contracts/conformance_matrix_v1_0.md`](conformance_matrix_v1_0.md).

## 5. Evidence example (DET-001)

- Comparison report path format: `reports/determinism_compare_v1/<date>/DET-001/<platform-a>__<platform-b>/comparison.json`.
- Platform fingerprint artifacts and platform-specific manifest hashes may differ across platforms and are not part of DET equality checks.
- Current DET-001 reference example demonstrates OS-level reproducibility on Windows x64 vs Linux x64 using WSL2 on one host; multi-host reproducibility evidence remains TBD.
