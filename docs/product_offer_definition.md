# RuleDSL ? Product Offer Model

## Target Customer Profile
RuleDSL is aimed at mid-market software companies that run business-critical decision logic inside their own applications.

Typical organizations are large enough to have dedicated engineering ownership for integration, but small enough to prefer low-touch adoption over heavy consulting engagement.

The expected engineering maturity is practical and delivery-focused: teams can integrate a C SDK, manage build/runtime dependencies, and maintain internal observability.

Common use cases include policy decisioning, limit checks, compliance gating, and deterministic scoring paths where decisions must be explainable and repeatable.

These teams care about determinism because operational confidence depends on reproducible behavior across environments, releases, and incident investigations.

## What We Provide
- Redistributable SDK package with headers, binaries, and integration notes.
- Core documentation covering ABI contract, ownership, thread model, replay, and error model.
- Minimal example code for initial compile/run validation.
- Structured evaluation framework for deterministic fit and migration risk assessment.
- Optional time-boxed integration advisory focused on architecture and risk controls.

## What We Do Not Provide
- 24/7 operational SLA.
- Customer-specific feature development on demand.
- On-site consulting as part of the base offer.
- Managed hosting or runtime operation of customer workloads.

## Engagement Model
- Initial 30-day evaluation focused on technical fit and operational risk validation.
- Fixed-scope integration support window with predefined technical outcomes.
- Annual license model at a high level, with scope defined by deployment and support terms.

## Customer Responsibilities
- Own the integration boundary and internal abstraction around SDK usage.
- Own runtime environment provisioning, hardening, and release process.
- Own operational monitoring, alerting, and incident response.
- Own upgrade lifecycle planning, compatibility checks, and rollout controls.
