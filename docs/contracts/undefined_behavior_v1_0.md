# Undefined Behavior Boundaries (v1.0)

This document defines strict undefined behavior boundaries for RuleDSL 1.0 determinism scope.

## Undefined behavior list

- [DET-011] Passing malformed or truncated bytecode to evaluation APIs is undefined behavior.
- [DET-012] Passing bytecode with unsupported format/version markers is undefined behavior unless an explicit compatibility error is returned.
- [DET-013] Supplying non-normalized input (including duplicate keys or unstable field ordering) is undefined behavior for determinism claims.
- [DET-014] Mutating input buffers concurrently with evaluation is undefined behavior.
- [DET-015] Passing invalid pointers, invalid sizes, or mismatched ownership across the public C API is undefined behavior.
- [DET-016] Writing to reserved API fields without explicit version documentation is undefined behavior.
- [DET-017] Depending on unspecified default option values is undefined behavior when an option is documented as required.
- [DET-018] Invoking evaluation on unsupported platforms is undefined behavior for this contract.
- [DET-019] Assuming deterministic output from non-finite numeric inputs is undefined behavior unless explicitly documented.
- [DET-020] Assuming deterministic behavior after API-level contract violations (lifetime, threading, aliasing) is undefined behavior.

## Enforcement note

Implementations SHOULD fail fast with stable error codes when undefined behavior is detected, but detection coverage is not guaranteed.
