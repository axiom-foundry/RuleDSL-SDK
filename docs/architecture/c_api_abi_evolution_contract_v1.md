# C API / ABI Evolution Contract v1

- Status: DRAFT
- Version: 1.0
- Date: 2026-02-22
- Scope: public C API/ABI compatibility for RuleDSL v1.x

## 1. Purpose

This contract defines how the public C API/ABI evolves without breaking integrators. All ABI-visible changes MUST comply with these rules.

## 2. ABI extension pattern

Public ABI structures SHALL follow this forward-compatible pattern:

- `struct_size`: caller-populated byte size of the struct instance.
- `version`: explicit struct contract version.
- `reserved[]`: zero-initialized reserved slots for future additive expansion.

Rules:

- Callers MUST set `struct_size` and `version` correctly for the used header version.
- Callers SHALL zero-initialize all `reserved` fields.
- Callees MUST validate `struct_size`/`version` before reading optional fields.
- If `struct_size` is smaller than required for a field, callee SHALL treat that field as absent.
- Callees SHALL reject incompatible versions with stable error signaling.

## 3. Enum evolution policy

Enum evolution is additive-only in v1.x:

- Existing enum numeric values MUST NOT be renumbered or repurposed.
- New enum values MAY be appended.
- Consumers SHOULD include unknown-value handling.
- Providers MUST return a stable fallback error when unknown enum input is not supported.

## 4. Error reporting policy

Error surface rules:

- Stable numeric error codes are contractual and MUST remain stable within v1.x.
- Error strings are optional and informational unless explicitly versioned as contractual.
- Integrators SHALL NOT build logic that depends only on free-form error text.
- Implementations MUST provide code-first error classification.

## 5. Ownership and memory policy

Ownership rules:

- The allocator/freeing contract for each API output MUST be explicit in API docs.
- The component that allocates a returned buffer SHALL provide the matching free path.
- Cross-allocator frees are PROHIBITED.
- Consumers MUST release owned buffers exactly once.

## 6. Thread-safety model

Threading model summary:

- API calls are thread-safe only where explicitly documented.
- Per-evaluation state SHOULD be isolated and reentrant.
- Shared mutable global state affecting evaluation outcomes is PROHIBITED.
- Per-evaluation options MUST be passed explicitly; implicit thread-global options are disallowed.

## 7. Determinism boundary reminders

Determinism constraints for ABI usage:

- Current time/now values MUST be injected explicitly as input/options.
- Locale-dependent formatting/parsing in deterministic surfaces is PROHIBITED.
- Ordering in deterministic outputs MUST be stable and explicitly defined.
- ABI evolution SHALL NOT introduce nondeterministic defaults.

## 8. Compatibility decision matrix

- Additive optional field + safe default: ALLOWED in v1.x.
- Additive enum member + unknown handling preserved: ALLOWED in v1.x.
- Existing struct layout/meaning break: REQUIRES major version.
- Existing error code semantic change: REQUIRES major version.

This contract is normative for public C API/ABI evolution in v1.x.
