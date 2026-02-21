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
| RFC002-REQ-001 | 2. Determinism Definition | Determinism claims evaluated only when engine/version/abi/bytecode/input/options are identical. | PARTIAL | `Tools/replay_proof/verify_replay_proof.py` with `python Tools/replay_proof/verify_replay_proof.py --a Tools/replay_proof/fixtures/pass_a.json --b Tools/replay_proof/fixtures/pass_b.json --strict` | TODO: add `evaluation_options_hash` to replay record and enforce in strict verifier. |
| RFC002-REQ-002 | 2. Determinism Definition | Under preconditions, identical `decision_hash` SHALL be produced. | PARTIAL | `Tools/replay_proof/verify_replay_proof.py` + `Tools/replay_proof/fixtures/pass_a.json` / `Tools/replay_proof/fixtures/pass_b.json` | TODO: add generated-record integration test from real engine output in public CI artifact checks. |
| RFC002-REQ-003 | 2. Determinism Definition | Under preconditions, identical `error_code` SHALL be produced when error exists. | PARTIAL | `Tools/replay_proof/verify_replay_proof.py` (compares `error_code` when present in both records) | TODO: add explicit failing-input fixtures with non-zero `error_code` equality assertions. |
| RFC002-REQ-004 | 2. Determinism Definition | Under preconditions, identical structural validation outcome SHALL be produced. | MISSING | (none) | TODO: add a validation outcome field in replay records and test matching status across repeated runs. |
| RFC002-REQ-005 | 2. Determinism Definition | If listed inputs differ, determinism guarantees are void for comparison. | PARTIAL | `python Tools/replay_proof/verify_replay_proof.py --a Tools/replay_proof/fixtures/pass_a.json --b Tools/replay_proof/fixtures/fail_mismatch_decision.json --strict` | TODO: add mismatch fixtures for engine version, ABI, bytecode hash, and input hash individually. |
| RFC002-REQ-006 | 3. Deterministic Surfaces | Surfaces marked NO SHALL be out of determinism scope. | MISSING | (none) | TODO: add governance lint/check that out-of-scope surfaces are never used as equality gates. |
| RFC002-REQ-007 | 4. Numeric Model Contract | Floating-point evaluation SHALL use IEEE-754 binary64 semantics. | MISSING | (none) | TODO: add numeric conformance suite evidence linkage (public matrix row pointing to engine test evidence artifact). |
| RFC002-REQ-008 | 4. Numeric Model Contract | Rounding mode SHALL be ties-to-even. | MISSING | (none) | TODO: add deterministic rounding edge-case vectors and expected decision hash outputs. |
| RFC002-REQ-009 | 4. Numeric Model Contract | Fast-math optimizations that alter numeric results are PROHIBITED. | MISSING | (none) | TODO: add build metadata check proving deterministic compiler flags for release artifacts. |
| RFC002-REQ-010 | 4. Numeric Model Contract | Undefined behavior in numeric evaluation is PROHIBITED. | MISSING | (none) | TODO: add UB-focused negative tests and explicit deterministic error assertions. |
| RFC002-REQ-011 | 5. Error Determinism | Identical invalid inputs SHALL emit identical `error_code`. | MISSING | (none) | TODO: add replay fixtures for invalid inputs and strict compare of `error_code`. |
| RFC002-REQ-012 | 6. Evidence Mapping | Equality proof MUST match engine_version_string, abi_level, bytecode_hash, input_hash, decision_hash. | COVERED | `Tools/replay_proof/verify_replay_proof.py` with strict mode (`--strict`) and fixtures in `Tools/replay_proof/fixtures/` | Strict verifier enforces field equality and reports mismatches deterministically. |
| RFC002-REQ-013 | 7. Non-Goals | Determinism claims SHALL NOT extend across different engine major versions. | MISSING | (none) | TODO: add mismatch fixture pair showing engine major version divergence => FAIL. |
| RFC002-REQ-014 | 7. Non-Goals | Determinism claims SHALL NOT extend across different ABI levels. | MISSING | (none) | TODO: add ABI mismatch fixture pair and verify strict fail outcome. |
| RFC002-REQ-015 | 7. Non-Goals | Determinism claims SHALL NOT extend across builds using result-altering numeric flags. | MISSING | (none) | TODO: add evidence metadata field for numeric flags and mismatch policy check. |
| RFC002-REQ-016 | 7. Non-Goals | Determinism claims SHALL NOT extend across hardware when numeric model contract is violated. | MISSING | (none) | TODO: add cross-hardware comparison guidance and explicit invalid-claim marker in evidence docs. |
| RFC002-REQ-017 | 8. Stability Clause | RFC-002 requirement IDs SHALL remain stable across edits. | MISSING | (none) | TODO: add docs lint that fails if existing RFC002 IDs are changed or removed. |
| RFC002-REQ-018 | 8. Stability Clause | New normative requirements SHALL append IDs; existing IDs SHALL NOT be renumbered. | MISSING | (none) | TODO: add append-only ID ordering check in governance docs validation script. |

## Priority Backlog (Top 10)

1. Add generated replay-record integration test from real engine run artifacts and verify strict equality (`private repo`, cross-platform, smoke).
2. Add mismatch fixtures for each precondition field (engine/abi/bytecode/input/options) (`public repo`, smoke).
3. Add invalid-input replay fixtures that assert stable non-zero `error_code` (`public repo`, smoke).
4. Add structural validation outcome field to replay schema and strict verifier enforcement (`public + private`, smoke).
5. Add numeric edge-case vector suite (ties-to-even rounding) and expected deterministic outputs (`private repo`, cross-platform, long-running).
6. Add release artifact metadata check for prohibited numeric flags (`private repo`, smoke).
7. Add governance lint for RFC002 ID stability and append-only policy (`public repo`, smoke).
8. Add cross-hardware evidence publication policy test gate (claim requires comparison artifact) (`public repo`, smoke).
9. Add deterministic JSON serialization conformance tests for replay record producers (`public repo`, smoke).
10. Add explicit out-of-scope surface policy check (timestamp/network/fs/thread data excluded from equality) (`public repo`, smoke).
