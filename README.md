# RuleDSL SDK (C API)

RuleDSL is a **deterministic rule-evaluation engine** embedded via a stable C ABI.
Same input, same bytecode, same decision — guaranteed across supported platforms.

**Use cases**: transaction risk scoring, spending-limit enforcement, compliance gating, offer eligibility, real-time policy evaluation.

**What it is**: an in-process library (`.dll` / `.so`). No daemon, no network hop, no database dependency.

**What it is not**: not a SaaS, not an open-source engine, not a 24/7 managed service.

> **Get started:** Download the latest bundle from [Releases](https://github.com/axiom-foundry/RuleDSL-SDK/releases). The bundle includes the engine library, compiler, headers, language bindings, and documentation — everything you need to integrate.

## Quickstart

Customer workflow: **Write -> Compile -> Verify -> Evaluate**

```
# 1. Write a rule
rule high_risk {
    when amount > 1000 and currency == "USD";
    then decline;
}

# 2. Compile to bytecode
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3

# 3. Verify bytecode integrity
ruledslc verify rules.axbc

# 4. Evaluate via C API (see examples/)
```

Minimal C integration:

```c
#include "axiom/ruledsl_c.h"

char err[256] = {0};
AXCompiler* c = ax_compiler_create();
ax_compiler_build(c, err, sizeof(err));

// Load bytecode from file (see examples/c/minimal_eval.c for full load_file helper)
AXBytecode bc = {0};
// ... load .axbc file into bc.data / bc.size ...

AXField fields[] = {
    { "amount",     { AX_VALUE_NUMBER, .number = 1200.0 } },
    { "currency",   { AX_VALUE_STRING, .text = "USD" } },
    { "now_utc_ms", { AX_VALUE_NUMBER, .number = 1700000000000.0 } },
};

AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
AXDecision dec = AX_DECISION_INIT;

AXErrorCode code = ax_eval_bytecode(c, &bc, fields, 3, &opts, &dec, err, sizeof(err));
if (code == AX_ERR_OK && dec.matched) {
    printf("Decision: %d\n", dec.action_type);  // AX_ACTION_DECLINE
}

ax_decision_reset(&dec);
ax_compiler_destroy(c);
```

## Engine Robustness

The RuleDSL engine is built to fail safe: malformed inputs are rejected gracefully with structured
error codes, never with a crash.

**Continuous fuzzing.** The parser and bytecode loader are exercised on every change by CI-gated,
coverage-guided fuzzing (libFuzzer under AddressSanitizer + UndefinedBehaviorSanitizer), seeded with a
committed adversarial corpus (malformed rule sources and tampered/truncated/oversized bytecode). This
continuous fuzzing caught — and let us fix — a real determinism bug (an integer overflow in priority
parsing) before release.

**Tested against** adversarial and edge-case scenarios on every release:

- Malformed rule sources and tampered bytecode (flipped bits, truncated files, wrong magic, oversized payloads) — rejected, never crash.
- Hostile input strings (injection-style payloads — SQL, markup, CRLF — null bytes, very long identifiers) — rejected.
- Rule-complexity limits and C-API misuse (NULL pointers, double-free, bad struct sizes, NaN/Infinity) — return proper error codes.
- Locale determinism — identical bytecode across OS locales (C, Turkish, German, French, POSIX, en_US, tr_TR).
- Concurrency — sustained multi-threaded stress (8 threads) and long sequential soak runs complete with zero crashes, zero errors, and no net memory growth; a shared compiler used across threads returns `AX_ERR_CONCURRENT_COMPILER_USE` rather than corrupting state.

**Performance shape.** Evaluation is in-process — no network hop, no serialization — and bytecode
evaluation avoids parsing on the hot path. Throughput scales with per-thread compilers; measure on
your target hardware and workload.

## What you receive

A delivery bundle (`.zip`) includes everything needed to integrate:

| Content | Description |
|---------|------------|
| `bin/` | Engine library (`.dll`/`.so`), compiler (`ruledslc`), import library |
| `include/` | C headers |
| `bindings/` | Python and C# wrappers with examples |
| `examples/` | Complete C examples with rule files |
| `docs/` | Cookbook, error reference, troubleshooting |
| `manifests/` | `MANIFEST.json`, `HASHES.txt` for integrity verification |

## Language bindings

Not a C developer? Use the ready-made wrappers:

| Language | Location | Dependencies |
|----------|----------|-------------|
| Python 3.7+ | [`bindings/python/`](bindings/python/README.md) | None (pure ctypes) |
| C# (.NET 6+) | [`bindings/csharp/`](bindings/csharp/README.md) | None (P/Invoke) |

## Documentation

| Topic | Document |
|-------|----------|
| **Rule cookbook** | [`docs/rule_cookbook.md`](docs/rule_cookbook.md) |
| Error handling | [`docs/errors.md`](docs/errors.md) |
| Troubleshooting | [`docs/troubleshooting.md`](docs/troubleshooting.md) |
| Integration snippets | [`docs/integration_snippets.md`](docs/integration_snippets.md) |

Full documentation index: [`docs/README.md`](docs/README.md)
