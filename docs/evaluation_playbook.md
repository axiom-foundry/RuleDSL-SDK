# Evaluation Playbook (30 Days)

## Public-facing summary

This playbook defines a structured evaluation process for RuleDSL SDK integration and operations readiness.

## Evaluation goals

- verify integration in target host boundary,
- verify deterministic behavior for fixed inputs,
- verify operational readiness (rollout and rollback),
- collect reproducible issue evidence.

## Roles

Vendor provides:

- runtime artifacts,
- headers,
- core documentation,
- minimal integration samples,
- approved bytecode samples when in scope.

Customer provides:

- target environment,
- integration owners,
- sanitized representative inputs,
- rollout/rollback operators.

## Phase flow (30 days)

- **Day 0-2**: preflight (version, environment, hashes, smoke).
- **Day 2-10**: integration and error-handling wiring.
- **Day 5-15**: determinism validation with replay samples.
- **Day 10-25**: staged rollout and rollback drill.
- **Day 25-30**: close-out decision and handoff.

## Required error-handling pattern

- always check `AXErrorCode`,
- capture code + detail on failure,
- do not parse detail text for control flow.

## Determinism validation criteria

Determinism claim applies when runtime version, bytecode hash, inputs, and options are identical.

Recommended evidence:

- sample set identifier,
- bytecode hash,
- run identifier,
- output comparison result.

## Bug bundle minimum

- runtime version,
- OS/arch,
- binary + bytecode hashes,
- API sequence summary,
- error code/detail,
- sanitized minimal repro,
- expected vs actual behavior.

## Success criteria

- stable integration,
- determinism checks pass,
- rollback drill passes,
- customer team can run baseline diagnostics using public docs.

## References

- `docs/errors.md`
- `docs/bytecode_lifecycle.md`
- `docs/version_policy.md`
- `docs/support_policy.md`