# Signing Policy

## A) Purpose

Detached signatures provide authenticity and tamper evidence for release integrity metadata.
In this model, a signature protects `SHA256SUMS.txt`, and `SHA256SUMS.txt` protects shipped artifacts by hash.

## B) What Is Signed

Recommended signed object:

- Detached signature over the exact bytes of `SHA256SUMS.txt`.

Notes:

- `manifest.json` can be covered indirectly because it SHOULD be listed in `SHA256SUMS.txt`.
- Signature payload is detached and stored as a separate file.

## C) Algorithms

Default policy algorithm:

- RSA PKCS#1 v1.5 with SHA-256 (`rsa-pkcs1v15-sha256`).

Rationale:

- Verifiable in the local Python verifier with no third-party dependencies.
- Supports offline verification.

## D) Key Lifecycle

- Key generation SHOULD be performed offline.
- Public keys MUST be distributed via a pinned keyring (`docs/signing_keys.json`) and/or bundled release metadata.
- Key rotation MUST introduce a new `key_id`.
- Revocation MUST mark the key as revoked in the keyring.

## E) Trust Model

- Trust root is the pinned keyring in this repository.
- Signature `key_id` MUST map to an active key in `docs/signing_keys.json`.
- Revoked or unknown keys are untrusted.

## F) Verification Steps

1. Verify detached signature over `SHA256SUMS.txt` (if provided).
2. Verify all artifact hashes in `SHA256SUMS.txt`.

Failure modes:

- missing signature
- invalid signature
- untrusted key
- unsupported algorithm

## G) Upgrade Path

- Phase 1: signature verification is OPTIONAL (missing signature -> WARN).
- Phase 2: signature verification becomes REQUIRED for selected distribution tiers (missing/invalid signature -> FAIL).

- Operational workflow: `docs/signing_runbook.md`
