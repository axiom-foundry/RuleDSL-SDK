# RFC-001 System Boundary (v1)

Status: DRAFT  
Version: 1.0  
Date: 2026-02-21  
Audience: SDK integrators, platform engineers, release/governance owners

## 1. Purpose

**[RFC001-REQ-001]** This RFC defines the RuleDSL system boundary for v1.0 and the minimum contractual surface that MUST be treated as stable for deterministic decision execution.

## 2. Definitions

- Engine: the deterministic RuleDSL runtime implementation that evaluates bytecode.
- SDK: the public integration surface (headers, contracts, docs, and operational tooling).
- Contract: normative requirements that define supported behavior and compatibility guarantees.
- Evidence: reproducible artifacts that demonstrate conformance to contractual claims.
- Host: the embedding application/process that provides inputs, options, and execution context.

## 3. Scope (what RuleDSL IS)

- **[RFC001-REQ-002]** RuleDSL SHALL provide deterministic decision evaluation for the documented contract surface.
- **[RFC001-REQ-003]** RuleDSL SHALL expose a stable public C ABI surface as documented in public headers and contract docs.
- **[RFC001-REQ-004]** RuleDSL SHALL consume compiled RuleDSL bytecode artifacts and host-provided inputs/options.
- **[RFC001-REQ-005]** RuleDSL SHALL produce decision outputs and stable numeric error/status codes on the supported surface.

## 4. Non-Goals (out of scope)

- **[RFC001-REQ-006]** RuleDSL MUST NOT be interpreted as a transport layer, API gateway, or network protocol.
- **[RFC001-REQ-007]** RuleDSL MUST NOT be interpreted as a persistence, workflow, scheduling, or orchestration system.
- **[RFC001-REQ-008]** RuleDSL MUST NOT be interpreted as a distributed consensus or multi-node state coordination system.
- RuleDSL SHOULD NOT be used as the source of truth for host identity, authentication, or policy distribution.

## 5. System Boundary

Trust boundary:
- Inputs, options, and bytecode provenance are host responsibilities until validated at the RuleDSL boundary.
- **[RFC001-REQ-009]** RuleDSL SHALL validate contract-visible fields and SHALL reject malformed boundary inputs on detectable paths.

Execution boundary:
- RuleDSL execution begins at public API entrypoints and ends at returned status/output artifacts.
- Behavior outside public API preconditions is outside the guaranteed surface.

## 6. Determinism Contract

Determinism is guaranteed only when all of the following hold:
- identical bytecode bytes,
- normalized input per contract,
- equivalent evaluation options,
- supported platform scope (Windows x64, Linux x64),
- defined contract-compliant usage.

**[RFC001-REQ-010]** Undefined behavior is prohibited in the specified surface; behavior outside contract is unspecified.

## 7. Responsibility Matrix

Engine responsibilities:
- **[RFC001-REQ-011]** Engine MUST preserve stable meaning of documented error/status codes.
- **[RFC001-REQ-012]** Engine MUST preserve deterministic evaluation semantics on the specified surface.
- **[RFC001-REQ-013]** Engine SHALL reject malformed contract-visible artifacts on supported detection paths.

Host responsibilities:
- **[RFC001-REQ-014]** Host MUST provide canonicalized input and explicit evaluation options required by contract.
- **[RFC001-REQ-015]** Host MUST treat unknown error/status codes as unknown failure states.
- **[RFC001-REQ-016]** Host SHALL not infer control flow from non-contractual diagnostic message bytes.
- **[RFC001-REQ-017]** Host SHALL manage integration lifecycle, retries, transport, persistence, and operational controls.

## 8. Failure Model

- Validation Error: input/options/bytecode contract checks fail at boundary; stable error/status code is returned when detectable.
- Execution Error: evaluation fails within defined runtime surface; stable error/status code is returned.
- Contract Violation: caller breaches preconditions; behavior is undefined outside guaranteed detection coverage.
- Determinism Breach: evidence indicates same-contract inputs did not yield same contract outputs; claim is non-conformant until resolved.

## 9. Version Governance

- **[RFC001-REQ-018]** Engine version, ABI level, and language version are separate governance axes and MUST be tracked independently.
- **[RFC001-REQ-019]** Compatibility claims SHALL identify all three axes in evidence/manifest context.
- **[RFC001-REQ-020]** Existing ABI elements MUST remain stable within major version unless explicitly versioned extensions are introduced.
- New capabilities MAY be added without redefining existing contract meanings.

## 10. Conformance and Evidence Hooks

A conformance claim SHOULD be backed by evidence including:
- bytecode fingerprint/hash,
- ABI level,
- manifest hashes,
- decision output hash (or canonical compare artifact hash),
- comparison report for cross-platform claims.

**[RFC001-REQ-021]** Evidence artifacts SHALL be reproducible and verifier-checkable on the documented surface.

## 11. Security and Safety Notes

- RuleDSL assumes no implicit network trust model.
- RuleDSL assumes no implicit persistence guarantees.
- RuleDSL assumes no distributed consensus semantics.
- Security controls for identity, authorization, transport security, and data retention remain host responsibilities.

## 12. Appendix A: Two-machine replay proof checklist

- Confirm both machines use a supported platform and declared ABI/language versions.
- Verify bytecode fingerprint equality before evaluation.
- Verify canonical input and options artifacts match by hash.
- Run evaluation on each machine with the same contract options.
- Compare canonical output artifact hashes and status codes.
- Record manifest/checksum evidence and comparison report for audit traceability.
