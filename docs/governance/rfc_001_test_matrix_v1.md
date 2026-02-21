# RFC-001 Test Coverage Matrix v1

- Status: DRAFT
- Source RFC: `docs/governance/rfc_001_system_boundary_v1.md`
- Date: 2026-02-21
- Purpose: ensure every normative requirement is testable and tracked

## Legend

- COVERED: a deterministic/contract test exists and is wired in CI (or at least in repo)
- PARTIAL: test exists but missing key variations / platforms / negative cases
- MISSING: no test exists yet

## Matrix

| Req ID | RFC Section | Normative Statement | Test Status | Test Pointer | Notes / Gaps |
| --- | --- | --- | --- | --- | --- |
| RFC001-REQ-001 | 1. Purpose | "...minimum contractual surface ... MUST be treated as stable for deterministic decision execution." | PARTIAL | `docs/contracts/error_codes_registry_v1_0.md`; `.github/workflows/verify-canonical.yml` (`Canonical header hash compare`) | Contract stability is documented and partially checked at header level; no end-to-end stability assertion for full boundary surface. |
| RFC001-REQ-002 | 3. Scope | "RuleDSL SHALL provide deterministic decision evaluation for the documented contract surface." | PARTIAL | `Tools/smoke/compiler_smoke_test.ps1` (`deterministic_hash_match` check) | Covers repeated compile/eval hash stability for examples; lacks cross-host matrix in public CI and broader input space. |
| RFC001-REQ-003 | 3. Scope | "RuleDSL SHALL expose a stable public C ABI surface..." | COVERED | `.github/workflows/verify-canonical.yml` (`Canonical header hash compare`) | CI enforces header canonicalization against engine reference; ABI binary compatibility tests are still outside public repo. |
| RFC001-REQ-004 | 3. Scope | "RuleDSL SHALL consume compiled RuleDSL bytecode artifacts and host-provided inputs/options." | PARTIAL | `Tools/smoke/compiler_smoke_test.ps1` (compile -> verify -> evaluate flow) | Happy-path covered through examples; missing malformed input matrix and fuzz-style boundary cases. |
| RFC001-REQ-005 | 3. Scope | "RuleDSL SHALL produce decision outputs and stable numeric error/status codes on the supported surface." | PARTIAL | `examples/*/expected_output.txt` + `Tools/smoke/compiler_smoke_test.ps1` | Decision outputs compared; numeric error-code stability not exhaustively asserted across API surfaces. |
| RFC001-REQ-006 | 4. Non-Goals | "RuleDSL MUST NOT be interpreted as a transport layer, API gateway, or network protocol." | MISSING | N/A | TODO: add governance lint that forbids network/transport claims in public contract pages. |
| RFC001-REQ-007 | 4. Non-Goals | "RuleDSL MUST NOT be interpreted as a persistence, workflow, scheduling, or orchestration system." | MISSING | N/A | TODO: add policy lint test for disallowed responsibility claims in docs. |
| RFC001-REQ-008 | 4. Non-Goals | "RuleDSL MUST NOT be interpreted as a distributed consensus or multi-node state coordination system." | MISSING | N/A | TODO: add docs-policy check for distributed-consensus claim language. |
| RFC001-REQ-009 | 5. System Boundary | "RuleDSL SHALL validate contract-visible fields and SHALL reject malformed boundary inputs on detectable paths." | PARTIAL | `Tools/smoke/compiler_smoke_test.ps1` (`ruledslc verify` STATUS=OK checks) | Positive verify path covered; negative malformed boundary cases are not systematically asserted in public CI. |
| RFC001-REQ-010 | 6. Determinism Contract | "Undefined behavior is prohibited in the specified surface; behavior outside contract is unspecified." | MISSING | N/A | TODO: add UB boundary negative tests mapped to contract-defined outcomes. |
| RFC001-REQ-011 | 7. Responsibility Matrix (Engine) | "Engine MUST preserve stable meaning of documented error/status codes." | PARTIAL | `.github/workflows/verify-canonical.yml` (`Canonical header hash compare`) | Registry exists; no automated numeric-value regression test in this repo. |
| RFC001-REQ-012 | 7. Responsibility Matrix (Engine) | "Engine MUST preserve deterministic evaluation semantics on the specified surface." | PARTIAL | `Tools/smoke/compiler_smoke_test.ps1`; `.github/workflows/verify-canonical.yml` (`verify` job) | Determinism smoke exists; limited scenario coverage and no mandatory cross-platform determinism compare in public repo. |
| RFC001-REQ-013 | 7. Responsibility Matrix (Engine) | "Engine SHALL reject malformed contract-visible artifacts on supported detection paths." | PARTIAL | `Tools/smoke/compiler_smoke_test.ps1` (`ruledslc verify`) | Detect/reject behavior only partially covered; missing malformed bytecode/input corpus tests. |
| RFC001-REQ-014 | 7. Responsibility Matrix (Host) | "Host MUST provide canonicalized input and explicit evaluation options required by contract." | MISSING | N/A | TODO: add host integration tests that fail on non-canonical input and missing required options. |
| RFC001-REQ-015 | 7. Responsibility Matrix (Host) | "Host MUST treat unknown error/status codes as unknown failure states." | MISSING | N/A | TODO: add C example/unit test for unknown code handling fallback branch. |
| RFC001-REQ-016 | 7. Responsibility Matrix (Host) | "Host SHALL not infer control flow from non-contractual diagnostic message bytes." | MISSING | N/A | TODO: add lint/check that integration examples branch on codes only, not message strings. |
| RFC001-REQ-017 | 7. Responsibility Matrix (Host) | "Host SHALL manage integration lifecycle, retries, transport, persistence, and operational controls." | MISSING | N/A | Out-of-engine responsibility; requires operational playbook checks, not present as executable tests. |
| RFC001-REQ-018 | 9. Version Governance | "Engine version, ABI level, and language version ... MUST be tracked independently." | PARTIAL | `Tools/release_bundle/build_bundle.ps1` (`engine_version`, `lang_version`, `abi_level`) | Fields are generated in bundle manifests; no CI assertion in public verify workflow for field presence/consistency. |
| RFC001-REQ-019 | 9. Version Governance | "Compatibility claims SHALL identify all three axes in evidence/manifest context." | PARTIAL | `Tools/release_bundle/build_bundle.ps1`; `Tools/release_bundle/audit_bundle_layout.ps1` | Manifest + hash structure checked; claim-level semantic validation still missing. |
| RFC001-REQ-020 | 9. Version Governance | "Existing ABI elements MUST remain stable within major version..." | PARTIAL | `.github/workflows/verify-canonical.yml` (`Canonical header hash compare`) | Header equivalence checked; ABI binary/layout drift tests are not in public repo. |
| RFC001-REQ-021 | 10. Conformance and Evidence Hooks | "Evidence artifacts SHALL be reproducible and verifier-checkable on the documented surface." | PARTIAL | `Tools/release_bundle/audit_bundle_layout.ps1`; `Tools/smoke/compiler_smoke_test.ps1` | Reproducibility checks exist for release/smoke flows; RFC-001-specific evidence verifier matrix is incomplete. |

## Priority Backlog (ordered)

1. Add RFC-001 determinism replay golden test (same bytecode/input/options twice -> same decision hash) under `Tools/smoke/tests/rfc001_det_replay.ps1`.
2. Add malformed bytecode rejection matrix test (truncated/corrupt/unsupported marker) under `Tools/smoke/tests/rfc001_malformed_bytecode.ps1`.
3. Add unknown `AX_ERR_*` handling test for host examples under `examples/tests/rfc001_unknown_error_handling.c`.
4. Add non-canonical input rejection test (duplicate keys/unstable ordering) under `Tools/smoke/tests/rfc001_input_canonicalization.ps1`.
5. Add required options enforcement test (missing `now_utc_ms`, wrong type) under `Tools/smoke/tests/rfc001_required_options.ps1`.
6. Add ABI numeric-code regression test (header enum values frozen) under `Tools/smoke/tests/rfc001_error_code_freeze.ps1`.
7. Add docs governance lint for non-goal boundary claims under `Tools/smoke/tests/rfc001_non_goal_doc_lint.ps1`.
8. Add message-bytes non-contractual compliance test for examples (no control flow on detail text) under `examples/tests/rfc001_no_message_control_flow.c`.
9. Add compatibility-axes manifest assertion test (`engine_version`, `abi_level`, `lang_version`) under `Tools/release_bundle/tests/rfc001_manifest_axes.ps1`.
10. Add conformance artifact reproducibility check (manifest/HASHES repeatability) under `Tools/release_bundle/tests/rfc001_evidence_reproducibility.ps1`.
