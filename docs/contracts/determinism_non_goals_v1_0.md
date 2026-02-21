# Determinism Non-Goals (v1.0)

This document defines what the RuleDSL 1.0 determinism contract does not guarantee.

## Non-goals

- The contract MUST NOT be interpreted as a guarantee that different bytecode artifacts yield equivalent outcomes, even if produced from similar source rules.
- The contract MUST NOT be interpreted as cross-version bytecode compatibility.
- The contract MUST NOT be interpreted as output equivalence across unsupported platforms or architectures.
- The contract MUST NOT be interpreted as deterministic behavior for malformed inputs or undefined API usage.
- The contract MUST NOT be interpreted as guaranteeing identical performance, latency, or memory footprint.
- The contract MUST NOT be interpreted as preserving internal engine diagnostics text byte-for-byte across patch versions.
- The contract SHOULD NOT be interpreted as legal or regulatory correctness of rule outcomes.
