# Support Scope and Model

## Public-facing summary

This document defines the support scope and model for public RuleDSL SDK deliveries.

RuleDSL is built to minimize the need for support. Evaluation is deterministic and reproducible;
failures surface through a stable, structured error-code contract (see `docs/errors.md`) rather than
opaque crashes; and the documentation set is designed for self-service integration. Support is
offered on a best-effort basis on top of that foundation — the goal is that you rarely need it.

## Supported scope

Supported baseline:

- OS families: Windows and Linux
- Architecture baseline: x64
- Integration toolchains: MSVC, clang, gcc

Supported interface:

- public C API and documented behavior only.

Support means reproducible triage on supported releases and fix delivery through hotfix or scheduled PATCH releases.

## Channels and hours

- Business-day support model by default.
- Targets are time-to-first-response, not guaranteed time-to-resolution.
- Contact endpoints are provided during onboarding.

## Severity model

- **Sev1**: production outage, corruption risk, or active security incident.
- **Sev2**: major degradation or rollout/integration blocker.
- **Sev3**: non-blocking defects, questions, documentation clarifications.

## Response handling (best-effort, by severity)

Support is best-effort and prioritized by severity; response times are guidance, not contractual
commitments. Higher-severity issues are handled first:

- Sev1: handled first.
- Sev2: next priority.
- Sev3: handled as capacity allows.

A complete incident bundle (below) is the fastest path to a resolution.

## Required incident bundle

Issue reports SHOULD include:

- runtime version string,
- OS/arch,
- binary and bytecode SHA-256,
- error code and detail,
- minimal sanitized repro,
- expected vs actual result.

Without this bundle, triage may be delayed.

## Fix delivery policy

- Hotfix: Sev1/security on supported lines.
- Scheduled patch: normal issues grouped into next PATCH release.
- PATCH releases MUST NOT break ABI.

## Out-of-scope boundaries

Out of scope by default:

- custom one-off engine changes,
- unsupported environments,
- host-application defects,
- guaranteed workload-specific tuning outcomes,
- emergency on-call unless separately contracted.

## References

- `docs/version_policy.md`
- `docs/errors.md`
- `docs/evaluation_playbook.md`
- `docs/bytecode_lifecycle.md`