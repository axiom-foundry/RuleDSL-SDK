# RFC-002 Test Coverage Matrix v1

- Status: DRAFT
- Source RFC: `docs/governance/rfc_002_determinism_scope_v1.md`
- Date: 2026-02-21
- Purpose: ensure every RFC002-REQ-### requirement is test-backed and tracked

## Legend

- COVERED: test exists (in repo) with concrete pointer (path + test name/command)
- PARTIAL: test exists but missing critical variations (platform, negative case, strict mode, etc.)
- MISSING: no test exists yet; include an explicit TODO describing the test

## Canonical ID Policy

- RFC-002 defines canonical requirement IDs (`RFC002-REQ-###`).
- The matrix MUST track those IDs verbatim; IDs are stable even if text evolves.

## Matrix

| Req ID | RFC Section | Normative Statement (trimmed) | Test Status | Test Pointer | Notes / Gaps |
|---|---|---|---|---|---|
| RFC002-REQ-001 | 2. Determinism Definition | Determinism claims evaluated only when engine/version/abi/bytecode/input/options are identical. | COVERED | `Tools/replay_proof/test_verify_replay_proof.py --generated-a <A> --generated-b <B>` under `--strict` internally, plus `Tools/replay_proof/verify_replay_proof.py` | Real generated records pin input and canonical options; individual engine/ABI/bytecode/input/options mutations are rejected. |
| RFC002-REQ-002 | 2. Determinism Definition | Under preconditions, identical `decision_hash` SHALL be produced. | COVERED | Real-engine producer/strict-verifier loops in `.github/workflows/surface-integrity.yml` and `.github/workflows/windows-fidelity.yml` | Linux and Windows CI generate two independent records from repeated real evaluations and require strict equality. |
| RFC002-REQ-003 | 2. Determinism Definition | Under preconditions, identical `error_code` SHALL be produced when error exists. | PARTIAL | `Tools/replay_proof/verify_replay_proof.py` (compares `error_code` when present in both records) | TODO: add explicit failing-input fixtures with non-zero `error_code` equality assertions. |
| RFC002-REQ-004 | 2. Determinism Definition | Under preconditions, identical structural validation outcome SHALL be produced. | PARTIAL | `bindings/python/examples/replay_proof_producer.py` and generated-record mutations in `Tools/replay_proof/test_verify_replay_proof.py` | Repeated successful `OK`/`0` outcomes and mismatches are covered; a producer path for non-OK validation evidence remains TODO. |
| RFC002-REQ-005 | 2. Determinism Definition | If listed inputs differ, determinism guarantees are void for comparison. | COVERED | Generated-record strict mutations in `Tools/replay_proof/test_verify_replay_proof.py` | Engine version, ABI, bytecode, decision, input, options, and validation surfaces are mutated independently and rejected. |
| RFC002-REQ-006 | 3. Deterministic Surfaces | Surfaces marked NO SHALL be out of determinism scope. | MISSING | (none) | TODO: add governance lint/check that out-of-scope surfaces are never used as equality gates. |
| RFC002-REQ-007 | 4. Numeric Model Contract | Floating-point evaluation SHALL use IEEE-754 binary64 semantics. | MISSING | (none) | TODO: add numeric conformance suite evidence linkage (public matrix row pointing to engine test evidence artifact). |
| RFC002-REQ-008 | 4. Numeric Model Contract | Rounding mode SHALL be ties-to-even. | MISSING | (none) | TODO: add deterministic rounding edge-case vectors and expected decision hash outputs. |
| RFC002-REQ-009 | 4. Numeric Model Contract | Fast-math optimizations that alter numeric results are PROHIBITED. | MISSING | (none) | TODO: add build metadata check proving deterministic compiler flags for release artifacts. |
| RFC002-REQ-010 | 4. Numeric Model Contract | Undefined behavior in numeric evaluation is PROHIBITED. | PARTIAL | engine fuzz CI (`.github/workflows/fuzz.yml`, libFuzzer under `-fsanitize=undefined`) | UBSan-instrumented continuous fuzzing exercises numeric evaluation for undefined behavior; targeted negative unit tests still TODO. |
| RFC002-REQ-011 | 5. Error Determinism | Identical invalid inputs SHALL emit identical `error_code`. | MISSING | (none) | TODO: add replay fixtures for invalid inputs and strict compare of `error_code`. |
| RFC002-REQ-012 | 6. Evidence Mapping | Equality proof MUST match engine_version_string, abi_level, bytecode_hash, input_hash, decision_hash. | COVERED | `Tools/replay_proof/verify_replay_proof.py` and generated-record strict mutations in `Tools/replay_proof/test_verify_replay_proof.py` | Strict verifier enforces the required mapping and reports each mismatch deterministically. |
| RFC002-REQ-013 | 7. Non-Goals | Determinism claims SHALL NOT extend across different engine major versions. | COVERED | `generated_mismatch_engine_version_string_strict` in `Tools/replay_proof/test_verify_replay_proof.py` | A generated peer record changed to RuleDSL 2.x is rejected under strict comparison. |
| RFC002-REQ-014 | 7. Non-Goals | Determinism claims SHALL NOT extend across different ABI levels. | COVERED | `generated_mismatch_abi_level_strict` in `Tools/replay_proof/test_verify_replay_proof.py` | A generated peer record with a changed ABI is rejected under strict comparison. |
| RFC002-REQ-015 | 7. Non-Goals | Determinism claims SHALL NOT extend across builds using result-altering numeric flags. | MISSING | (none) | TODO: add evidence metadata field for numeric flags and mismatch policy check. |
| RFC002-REQ-016 | 7. Non-Goals | Determinism claims SHALL NOT extend across hardware when numeric model contract is violated. | MISSING | (none) | TODO: add cross-hardware comparison guidance and explicit invalid-claim marker in evidence docs. |
| RFC002-REQ-017 | 8. Stability Clause | RFC-002 requirement IDs SHALL remain stable across edits. | MISSING | (none) | TODO: add docs lint that fails if existing RFC002 IDs are changed or removed. |
| RFC002-REQ-018 | 8. Stability Clause | New normative requirements SHALL append IDs; existing IDs SHALL NOT be renumbered. | MISSING | (none) | TODO: add append-only ID ordering check in governance docs validation script. |

## Priority Backlog (remaining)

1. Add invalid-input replay records that assert stable non-zero `error_code` (SDK, smoke).
2. Add a producer path for non-OK structural validation evidence and compare repeated failures (SDK, smoke).
3. Add numeric edge-case vectors (ties-to-even rounding) and expected deterministic outputs (engine-side, cross-platform, long-running).
4. Add release artifact metadata checks for prohibited numeric flags (engine-side, smoke).
5. Add governance lint for RFC002 ID stability and append-only policy (SDK, smoke).
6. Add a cross-hardware evidence publication policy gate (claim requires a comparison artifact) (SDK, smoke).
7. Add non-empty evaluation-options canonical JSON conformance vectors for replay producers (SDK, smoke).
8. Add an explicit out-of-scope surface policy check (timestamp/network/fs/thread data excluded from equality) (SDK, smoke).
9. Retain strict Windows/Linux generated records and their cross-platform report as CI evidence artifacts (SDK, cross-platform).
10. Add additive-v1 schema compatibility vectors for future optional evidence fields (SDK, smoke).
