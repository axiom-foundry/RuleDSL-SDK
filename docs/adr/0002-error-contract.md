# ADR-0002: Error contract

## Status

Accepted

## Context

Error handling must be stable for integration logic, conformance checks, and replay verification. Free-form messages vary across runtime environments and are not safe as the primary contract key.

## Decision

Numeric error codes are the primary public error contract.

- Stable numeric codes MUST preserve meaning within a major version.
- Message text is optional and informational unless explicitly versioned as contractual.
- Consumers MUST branch on numeric code, not message wording.
- Unknown codes SHOULD be handled as unknown error class with safe fallback.

## Consequences

- Error behavior is machine-verifiable across updates.
- Determinism and replay assertions can rely on code parity.
- Localization or wording changes do not break integrations.
- Registry governance for new codes remains required.
