# RuleDSL - Deterministic Decision Core

## What It Is
RuleDSL is an in-process rule and decision engine exposed through a C SDK. The host application links the SDK and calls it directly, with no runtime service dependency.

The SDK executes precompiled bytecode and returns structured decision outputs. It does not require a database layer, message broker, or sidecar process to evaluate decisions.

The public C interface is ABI-oriented and designed for long-lived integrations. The contract uses explicit struct metadata and compatibility fields to support safe extension.

Determinism is a first-class constraint in the engine contract. For equivalent bytecode and input payloads, evaluation behavior is expected to remain stable within documented platform assumptions.

## Why It Is Different
- Deterministic evaluation model
- ABI compatibility contract (`struct_size` + `reserved`)
- Replay schema with explicit header and integrity checks
- No runtime service
- No database requirement
- Concurrency-safe usage contract

## Integration Model
The host loads bytecode into memory, prepares input fields, executes evaluation, and consumes a structured decision object. Replay capture is optional and uses caller-provided buffers.

```text
compiler = create_compiler()
bc = load_bytecode(file)
input = { amount, currency, now_utc_ms, ... }
decision = eval_bytecode(compiler, bc, input)
if replay_enabled:
    replay_blob = record_replay_data(bc, decision)
```

## Risk Surface
- Frozen error code registry
- Explicit thread model
- Ownership/lifetime contract
- Runtime version fingerprint API

## Typical Use Cases
- Transaction policy evaluation in payment flows
- Spending and velocity limit checks
- Embedded fintech rule logic inside existing services
- Rule-based allow/deny/review routing in compliance workflows
- Local decision execution in latency-sensitive applications
