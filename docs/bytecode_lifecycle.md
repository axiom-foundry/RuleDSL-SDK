# Bytecode Lifecycle

## Public-facing summary

This document defines operational lifecycle expectations for shipped `.axbc` artifacts.

## Artifact flow

1. Rule definitions are compiled into `.axbc`.
2. Approved `.axbc` artifacts are versioned and hashed.
3. Hosts load bytecode bytes into memory.
4. Runtime evaluates decisions deterministically.

Phase-1 ownership model:

- Vendor supplies approved bytecode artifacts.
- Customer integrates and executes with the public SDK surface.

## Artifact identity and provenance

Track each bytecode artifact with:

- runtime version string,
- bytecode schema/version,
- SHA-256 of exact bytes,
- build timestamp for operations tracking,
- optional signature metadata.

Timestamps are for tracking only and are not determinism inputs.

## Determinism boundary

Evaluation determinism applies when all are fixed:

- runtime version,
- bytecode bytes,
- input fields,
- evaluation options.

## Runtime compatibility checks

Before evaluation, implementations SHOULD validate:

- header/magic integrity,
- schema compatibility,
- ABI-level compatibility expectations.

Incompatibility should be surfaced as stable public error codes.

## Rollout and rollback practice

Rollout:

- stage first,
- compare representative outputs,
- promote gradually.

Rollback:

- keep last-known-good artifacts,
- restore by artifact switch,
- re-run smoke verification.

## What to avoid

- mixing incompatible runtime/bytecode versions,
- editing `.axbc` by hand,
- deriving control flow from error detail strings.

## References

- `docs/version_policy.md`
- `docs/distribution.md`
- `docs/errors.md`