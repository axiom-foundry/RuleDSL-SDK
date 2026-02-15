# Distribution Model

## Public Surface

This repository intentionally publishes only the SDK surface:
- public headers (`include/`)
- documentation (`docs/`)
- integration example source (`examples/`)

No private engine source, internal tooling, tests, or CI internals are included here.

## Binary Delivery Status

Current status: no redistributable SDK binaries are committed in this repository.

Evaluation binaries are delivered separately during technical evaluation or via release artifacts when published.

## Platform Notes

- Windows and Linux are supported at the SDK interface level.
- Header and sample code review can proceed immediately from this repo.
- Compile-and-run evaluation requires matching binary artifacts for the target platform/toolchain.
