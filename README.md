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
