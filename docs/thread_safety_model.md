# Thread Safety Model

## Allowed

- Concurrent evaluation calls are allowed when each call uses isolated input and output buffers.
- Read-only sharing of immutable bytecode buffers is allowed with external lifetime control.

## Forbidden

- Concurrent use of the same `AXCompiler` instance from multiple threads.
- Reusing the same decision output struct in multiple in-flight calls.

## Required usage pattern

- Use one compiler per thread or external synchronization for compiler calls.
- Use one `AXDecision` per evaluation call.
- Call `ax_decision_reset` before reusing decision structs.
