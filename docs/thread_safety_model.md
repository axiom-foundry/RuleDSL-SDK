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

## Lifetime and destruction

Concurrent *use* of one compiler is detectable: the engine reports
`AX_ERR_CONCURRENT_COMPILER_USE` (8). Destruction is not.

- Destroying an `AXCompiler` while any call on it is still running is
  **undefined behaviour**. `ax_compiler_destroy` cannot detect an in-flight
  call, and `AX_ERR_CONCURRENT_COMPILER_USE` does not cover it: that code
  reports two live calls, not a call against freed memory.
- The failure is not reliably loud. An observed signature is an evaluation
  that returns success with a populated decision but **silently empty output
  fields**, because the compiler-global output state it reads was freed
  between the evaluation and the read.
- The host is responsible for ordering: destruction must happen after every
  call on that compiler has returned. A destroy that races an evaluation is a
  host defect, not something the engine will report.

The same applies to a callback: `AXTraceCallback` runs **inside**
`ax_eval_bytecode`. Destroying the compiler from a trace callback frees it
under the very call that is running.

## Binding guarantees

The shipped Python (`RuleDSL`) and C# (`RuleDSLEngine`) wrappers implement the
required pattern, so hosts using them do not have to:

- A single per-instance lock serializes **all** native calls — including
  `version()`/`Version()` and `check_compatibility()`/`CheckCompatibility()`,
  not only compile and evaluate. One instance is safe to share across threads.
- The output-field read (`ax_eval_output_field_count`/`_at`) happens in the
  same critical section as the evaluation that produced it. This is required
  for correctness, not merely defensive: that state is compiler-global and the
  next evaluation overwrites it.
- `close()` / `Dispose()` waits for any in-flight call on the instance to
  return before destroying the compiler, and is idempotent.
- Calling from **inside** an in-flight call on the same thread — a Python
  `on_trace` callback, for instance — is refused with an explicit error rather
  than honoured, because there the destroy would free the compiler under the
  running call. Close after the call returns.
- Finalizers (`__del__`, `~RuleDSLEngine`) never block. If the lock is held or
  a call is in flight they skip destruction: a leaked compiler is reclaimed at
  process exit, a use-after-free is not recoverable.
- After close, every public call reports the binding's stable "closed" error
  (`AX_ERR_RUNTIME` / `ObjectDisposedException`), never an attribute or
  null-reference error.

For maximum throughput, use one engine instance per thread to avoid lock
contention; correctness does not require it.
