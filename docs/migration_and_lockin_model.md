# RuleDSL – Migration & Lock-In Model

## Source of Coupling
RuleDSL coupling is concentrated at the C ABI boundary. The host process depends on stable function signatures, struct contracts, and error code semantics rather than internal engine implementation details.

Integration happens through explicit SDK calls controlled by the host. The host decides where and how calls are made, what data is passed, and how failures are handled.

Bytecode artifacts are external inputs to the engine, not embedded engine state. This keeps policy delivery and runtime integration separable.

## Reversibility
The engine can be replaced behind a host-defined decision abstraction layer if the host avoids leaking engine-specific types beyond the integration boundary.

A practical pattern is to wrap RuleDSL in a narrow internal interface and keep business code dependent on that interface instead of direct SDK calls.

Caller-retained inputs allow deterministic validation during migration. The same inputs and bytecode can be re-evaluated in candidate implementations and the resulting decision records compared for equality with the offline replay-proof verifier (`Tools/replay_proof/verify_replay_proof.py`) before cutover.

## Bytecode Strategy
Treat bytecode as a versioned artifact with explicit provenance (schema/toolchain/version metadata) and immutable identifiers.

Compatibility should be evaluated against declared schema/ABI fields reported by `ax_check_bytecode_compatibility` (`AXCompatibilityInfo`) and `ax_version_string`, not assumptions based on build environment.

For rollout and rollback, use staged promotion: generate candidate bytecode, run canary traffic or re-evaluation checks, then promote; keep a last-known-good bytecode ready for immediate rollback.

## ABI Stability
The `struct_size` + `version` pattern provides explicit negotiation between caller and library and reduces ambiguity during upgrades.

Runtime version and bytecode-compatibility state should be read through `ax_version_string` and `ax_check_bytecode_compatibility` instead of compile-time assumptions about the engine build.

Forward-compatible extension is achieved by additive fields and reserved space, preserving existing layouts and call patterns.

## Exit Strategy
- Replace RuleDSL behind the same host-owned decision interface.
- Validate behavioral equivalence with golden input sets, comparing decision records via the offline replay-proof verifier.
- Run dual-evaluation in production shadow mode before switching decision authority.
- Keep rollback path active until error and drift thresholds remain within acceptance limits.
- Freeze integration contracts (ABI checks, error mapping, ownership rules) before final cutover.
