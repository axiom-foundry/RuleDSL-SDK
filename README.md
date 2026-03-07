# RuleDSL SDK (C API)

RuleDSL is a **deterministic rule-evaluation engine** embedded via a stable C ABI.
Same input, same bytecode, same decision — guaranteed across supported platforms.

**Use cases**: transaction risk scoring, spending-limit enforcement, compliance gating, offer eligibility, real-time policy evaluation.

**What it is**: an in-process library (`.dll` / `.so`). No daemon, no network hop, no database dependency.

**What it is not**: not a SaaS, not an open-source engine, not a 24/7 managed service.

## Quickstart

Customer workflow: **Write -> Compile -> Verify -> Evaluate**

```
# 1. Write a rule
rule high_risk {
    when amount > 1000 and currency == "USD";
    then decline;
}

# 2. Compile to bytecode
ruledslc compile rules.rule -o rules.axbc --lang 1.0 --target axbc3

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

The RuleDSL engine is tested against adversarial and edge-case scenarios across every release.
Zero tolerance for crashes — all malformed inputs are rejected gracefully with structured error codes.

```
 Category                            Tests    Crashes   Result
 ────────────────────────────────────────────────────────────────
 Fuzz (malformed rule sources)          45          0   PASS
 Bytecode tampering                     17          0   PASS
 Input injection (SQLi/XSS/CRLF)       37          0   PASS
 Memory stability (sequential)        500          0   PASS
 Rule complexity limits                 30          0   PASS
 Locale determinism                      7          0   PASS
 C API misuse (NULL/NaN/overflow)       48          0   PASS
 Multi-thread stress (8 threads)   800000          0   PASS
 ────────────────────────────────────────────────────────────────
 Total                             800684          0   ALL PASS
```

Highlights:

- **Thread safety**: 800K concurrent evaluations across 8 threads — zero errors, zero memory leak
- **Throughput**: 79,000+ evaluations/sec (8 threads, per-thread compiler pattern)
- **Memory**: flat after warm-up, returns below baseline after cleanup (+0.34 MB at peak, -2.21 MB post-free)
- **Contention detection**: shared compiler across threads returns `AX_ERR_CONCURRENT_COMPILER_USE` — no crash, no corruption
- **Fuzz**: null bytes, 10K-char names, 1000-rule files, binary garbage — all rejected, none crash
- **Bytecode tampering**: flipped bits, truncated files, wrong magic, 1 MB garbage — all detected
- **Locale determinism**: identical bytecode across 7 OS locales (C, Turkish, German, French, POSIX, en_US, tr_TR)
- **API misuse**: NULL pointers, double-free, bad struct sizes, NaN/Infinity — all return proper error codes

## What you receive

A delivery packet includes:

| Content | Source |
|---------|--------|
| `include/` C headers | This repository |
| `bin/` compiled binaries | Provided separately |
| `manifest.json` + `SHA256SUMS.txt` | Integrity verification |
| Documentation | This repository |
| Examples | `examples/` directory |

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
