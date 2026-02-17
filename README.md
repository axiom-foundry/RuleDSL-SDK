# RuleDSL SDK (C API)

RuleDSL is a deterministic rule-evaluation engine embedded via a stable C ABI.
This repository provides the **public SDK surface** (headers + documentation) used to integrate RuleDSL into host applications.

> Distribution model: controlled delivery of versioned release artifacts (headers + compiled binaries).  
> Binaries are provided separately as part of a commercial delivery packet.  
> Verification of release artifacts (hashes and optional signature) is required before integration (see distribution policy below).

## Docs index

- Start here (integration): [`docs/integration_snippets.md`](docs/integration_snippets.md)
- Error contract: [`docs/errors.md`](docs/errors.md)
- Versioning: [`docs/version_policy.md`](docs/version_policy.md)
- Support: [`docs/support_policy.md`](docs/support_policy.md)
- Distribution + verification: [`docs/distribution.md`](docs/distribution.md)
- Evaluation workflow: [`docs/evaluation_playbook.md`](docs/evaluation_playbook.md)
- Bytecode lifecycle: [`docs/bytecode_lifecycle.md`](docs/bytecode_lifecycle.md)
- Release gate: [`docs/release_gate.md`](docs/release_gate.md)
- Signing: [`docs/signing_policy.md`](docs/signing_policy.md), [`docs/signing_runbook.md`](docs/signing_runbook.md)

## Language Specification

- Contract snapshot: [`docs/language/status_v0_9.md`](docs/language/status_v0_9.md)
- Bytecode Workflow (v0.9): [`docs/bytecode_workflow_v0_9.md`](docs/bytecode_workflow_v0_9.md)

### Core Language Documents (v0.9)

- Full Specification: [`docs/language/spec_v0_9.md`](docs/language/spec_v0_9.md)
- Grammar Definition: [`docs/language/grammar_v0_9.md`](docs/language/grammar_v0_9.md)
- Lexical Core: [`docs/language/lexical_core_v0_9.md`](docs/language/lexical_core_v0_9.md)
- Numeric Model: [`docs/language/numeric_model_v0_9.md`](docs/language/numeric_model_v0_9.md)
- Status Snapshot: [`docs/language/status_v0_9.md`](docs/language/status_v0_9.md)

## Quickstart (integration)

Runtime artifacts (compiled binaries) are required in addition to these headers.

- Start here: [`docs/integration_snippets.md`](docs/integration_snippets.md)
- Error handling contract: [`docs/errors.md`](docs/errors.md)

## Core policies (operational contract)

These documents define the compatibility, support, and distribution guarantees:

- Version & compatibility: [`docs/version_policy.md`](docs/version_policy.md)
- Support scope & response targets: [`docs/support_policy.md`](docs/support_policy.md)
- Distribution + artifact verification: [`docs/distribution.md`](docs/distribution.md)
- Evaluation workflow + bug bundle expectations: [`docs/evaluation_playbook.md`](docs/evaluation_playbook.md)
- Bytecode lifecycle & rollout/rollback: [`docs/bytecode_lifecycle.md`](docs/bytecode_lifecycle.md)

## Release verification (recommended)

- Release gate (hash + manifest + optional signature verification): [`docs/release_gate.md`](docs/release_gate.md)
- Signing policy & runbook:
  - [`docs/signing_policy.md`](docs/signing_policy.md)
  - [`docs/signing_runbook.md`](docs/signing_runbook.md)

## What you receive in a delivery packet

A delivery packet typically includes:

- `include/` headers (this repository)
- `bin/` compiled binaries (provided separately)
- `manifest.json` + `SHA256SUMS.txt` (+ optional detached signature)
- Links to the policy documents above

## What this is not

- Not a hosted SaaS
- Not an open-source engine implementation
- Not a 24/7 managed service by default
