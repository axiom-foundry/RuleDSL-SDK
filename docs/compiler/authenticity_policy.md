# RuleDSL Compiler Authenticity Policy

## Scope

This policy defines how customers verify that a distributed `ruledslc` binary is an official build.

## Trust Model

- Official compiler binaries are distributed through controlled vendor channels.
- Each delivery includes SHA256 hashes for every distributed binary.
- A binary is trusted only when its SHA256 hash exactly matches the published official hash.

## Verification Steps

1. Obtain the official hash list from the delivery packet.
2. Compute local SHA256 for `ruledslc`.
3. Compare against the published value.
4. Reject the binary if the hash does not match exactly.

## Version Output Binding

`ruledslc --version` includes:

```text
BUILD_HASH=<short-hash>
```

`BUILD_HASH` is a build identity marker and MUST be checked together with SHA256 verification.
SHA256 is the authoritative authenticity check.

## What Is Considered a Trusted Build

A build is trusted when all of the following are true:
- acquired via approved distribution channel,
- SHA256 matches the official delivery manifest,
- reported `BUILD_HASH` matches release documentation.

## Out of Scope

- Public PKI signing requirements (future enhancement).
- Online activation or telemetry checks.