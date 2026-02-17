# Version and Patch Policy

## Public-facing summary

This document defines compatibility and support expectations for the public RuleDSL SDK surface.

## Scope of guarantees

The following are guaranteed for supported release lines:

- Stable public C API/ABI behavior within a MAJOR line.
- Deterministic evaluation for the same runtime version, bytecode bytes, inputs, and options.
- Bytecode compatibility according to the schema/support window policy below.

The following are not guaranteed:

- Identical performance on every host platform/workload.
- Undocumented behavior outside the public API contract.

## Semantic versioning rules

Version format: `MAJOR.MINOR.PATCH`.

- **PATCH**: bug/security fixes and hardening; MUST NOT break ABI.
- **MINOR**: additive changes; MUST NOT break ABI.
- **MAJOR**: may introduce intentional breaking API/ABI changes with migration guidance.

Deprecations may be introduced in MINOR releases; removals occur only in a later MAJOR.

## ABI policy

- Existing symbols and enum numeric values MUST remain stable in a MAJOR line.
- Public struct layout MUST NOT be reordered or shrunk.
- Forward-compatible growth SHOULD use `struct_size` + reserved fields where available.
- Breaking changes require a MAJOR version bump.

## Bytecode/schema compatibility

- PATCH releases keep schema compatibility within the same MINOR line.
- MINOR releases may add backward-compatible schema extensions.
- MAJOR releases may change schema compatibility boundaries.

Default runtime loading window:

- same MAJOR, current MINOR, and previous MINOR.
- artifacts outside the supported window SHOULD be rejected deterministically.

## Support window and cadence

- Supported lines: latest MINOR and previous MINOR in active MAJOR.
- For each supported MINOR, only latest PATCH receives fixes.
- Security targets (best-effort): critical within 5 business days, high within 15 business days.

## Release checklist (public contract)

Each release SHOULD include:

- version string,
- compatibility statement,
- deterministic validation evidence reference,
- SHA-256 hashes for distributed artifacts.

## References

- `docs/bytecode_lifecycle.md`
- `docs/errors.md`
- `docs/support_policy.md`