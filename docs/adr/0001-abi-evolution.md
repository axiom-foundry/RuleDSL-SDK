# ADR-0001: ABI evolution

## Status

Accepted

## Context

RuleDSL exposes a public C ABI used by hosts that cannot update in lockstep with engine internals. ABI drift without extension rules creates break risk and undermines published compatibility claims.

## Decision

RuleDSL uses additive ABI evolution for public structs.

- Extensible structs SHALL include `struct_size`, `version`, and `reserved` fields.
- Callers MUST initialize `struct_size` and `version` and zero `reserved` storage.
- Callees MUST validate `struct_size` and `version` before reading optional fields.
- New fields SHALL be append-only in v1.x.
- Incompatible struct metadata MUST fail with a stable contract error.

Enum handling is additive-only.

- Existing enum numeric values MUST NOT be renumbered or repurposed.
- New enum values MAY be appended.
- Consumers SHOULD treat unknown enum values as unsupported and fail safely.

## Consequences

- Public ABI growth remains forward-compatible within v1.x.
- Hosts can adopt newer SDK versions with predictable downgrade behavior.
- Validation failures are deterministic and auditable.
- Breaking ABI redesign still requires a major version transition.
