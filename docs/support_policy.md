# Support Scope + SLA Policy

## Public-facing summary

This policy defines operational support scope and response targets for public RuleDSL SDK deliveries.

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

## Response targets (supported lines)

- Sev1: first response within 1 business day.
- Sev2: first response within 3 business days.
- Sev3: first response within 5 business days (best effort).

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