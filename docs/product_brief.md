# Product Brief

## 1) What RuleDSL Is

RuleDSL is a deterministic business rule engine for production software systems.
It is integrated as an embedded component through a stable C API contract.

The engine implementation is private and distributed as compiled binaries.
Customers integrate with headers and binaries, not engine source code.

Distribution is controlled. Releases are delivered as versioned artifact sets with explicit integrity metadata.

## 2) What Problem It Solves

Many teams need policy and decision logic that is consistent across environments and reproducible over time.
RuleDSL addresses that requirement with deterministic evaluation and operationally controlled release packaging.

It is designed for teams that need to explain and reproduce outcomes, not just compute them once.
This is relevant for financial controls, risk checks, entitlement logic, and other policy-driven paths.

It also reduces integration ambiguity by enforcing a stable external contract:

- stable C ABI expectations
- explicit version and compatibility policy
- artifact hash verification for release intake
- documented operational playbooks for evaluation, incidents, and rollback

## 3) Core Technical Properties

Deterministic evaluation is a primary property.
For the same engine version, bytecode, inputs, and options, outputs are expected to be identical within documented bounds.

The integration surface is a public C API with ABI stability policy.
Version evolution is defined through explicit compatibility rules rather than implicit behavior.

Bytecode lifecycle ownership is operationally defined.
Compilation, artifact provenance, rollout, and rollback are treated as part of system reliability, not ad hoc process.

Release artifacts are integrity-verifiable.
`SHA256SUMS.txt` is the authoritative hash source, with optional detached signature verification available through release tooling.

Support operations follow a business-day model with severity-based response targets.
Issue handling is designed around reproducible bundles and stable error diagnostics.

## 4) What Customers Receive

A standard release package includes:

- versioned release folder (`RuleDSL-<version>/`)
- compiled runtime binaries
- public C headers
- `manifest.json` metadata
- `SHA256SUMS.txt` integrity list
- optional detached signature descriptor when enabled by release policy

Customers also receive the technical documentation set required for integration and operations.
The expected model is explicit and controlled, not self-serve binary discovery.

## 5) Evaluation Model

RuleDSL uses a structured 30-day evaluation model.
The objective is to validate technical fit, deterministic behavior, and operational readiness before commercial onboarding.

Evaluation includes:

- staged integration against customer-owned environment
- deterministic replay checks over representative sanitized inputs
- rollback drill execution with last-known-good artifacts
- issue reporting through a defined bug bundle template

Success criteria are based on reproducibility and operational clarity, not subjective acceptance.

## 6) Operational Boundaries

RuleDSL is delivered with clear boundaries:

- no engine source code distribution
- support and guarantees scoped to the documented public C API
- no implicit runtime mutation assumptions in the contract
- no guarantees for undocumented behavior

This boundary is intentional.
It enables a supportable integration model where observed behavior can be tied to versioned artifacts and documented policy.

## 7) What RuleDSL Is Not

RuleDSL is not positioned as:

- a hosted SaaS service
- an open-source rule engine distribution model
- a general-purpose scripting runtime
- a 24/7 managed operations service by default

Its operating model is embedded, deterministic, and controlled-distribution.

## 8) References

- `docs/evaluation_playbook.md`
- `docs/version_policy.md`
- `docs/support_policy.md`
- `docs/distribution.md`
