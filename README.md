# RuleDSL SDK (C API)

RuleDSL is a **deterministic rule-evaluation engine** embedded via a stable C ABI.
Same input, same bytecode, same decision — guaranteed across supported platforms.

**Linux & Windows x86_64 · release v1.0.2 · language version v0.9 (v1.0 = target spec).**

**Use cases**: transaction risk scoring, spending-limit enforcement, compliance gating, offer eligibility, real-time policy evaluation.

**What it is**: an in-process library (`.dll` / `.so`). No daemon, no network hop, no database dependency.

**What it is not**: not a SaaS, not an open-source engine, not a 24/7 managed service.

**Open vs closed.** This repository is the **SDK** — headers, language bindings, examples, documentation, and determinism evidence, source-available for integration. The **engine** ships as a licensed binary in [Releases](https://github.com/axiom-foundry/RuleDSL-SDK/releases), not as open source. See [`LICENSE`](LICENSE) and [`EVALUATION_TERMS.md`](EVALUATION_TERMS.md).

> **Get started:** Download the latest bundle from [Releases](https://github.com/axiom-foundry/RuleDSL-SDK/releases). The bundle includes the engine library, compiler, headers, language bindings, and documentation — everything you need to integrate.
>
> **See it before you integrate:** the [demos](https://axiom-foundry.github.io/RuleDSL-SDK/demos/) show the engine running live, and `pip install ruledsl` adds the desktop **workbench** (`ruledsl-workbench`) — author rules interactively, read the engine's decision trace, and replay production `.axbc` bytecode on your desk. Pure Python; the engine itself still comes from the bundle.

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

## Language version & conformance

The Quickstart compiles with `--lang 0.9`. The shipped engine implements **language version v0.9** — the honest, deterministic subset of the **v1.0** target specification. The v1.0 spec is the normative target; every place the engine differs from it is documented explicitly, so there are no hidden surprises:

- **Shipped behavior, and where it diverges from the v1.0 target** — [`docs/language/conformance_status_v0_9.md`](docs/language/conformance_status_v0_9.md)
- **The v1.0 target specification** — [`docs/language/spec_v1_0.md`](docs/language/spec_v1_0.md)

## Engine Robustness

The RuleDSL engine is built to fail safe: malformed inputs are rejected gracefully with structured
error codes, never with a crash.

**Continuous fuzzing.** The parser and bytecode loader are exercised on every change by CI-gated,
coverage-guided fuzzing (libFuzzer under AddressSanitizer + UndefinedBehaviorSanitizer), seeded with an
adversarial corpus (maintained in the engine repository; malformed rule sources and
tampered/truncated/oversized bytecode). This continuous fuzzing has caught — and let us fix — bugs
before release.

**Tested against** adversarial and edge-case scenarios on every release:

- Malformed rule sources and tampered bytecode (flipped bits, truncated files, wrong magic, oversized payloads) — rejected, never crash.
- Hostile input strings (injection-style payloads — SQL, markup, CRLF — null bytes, very long identifiers) — rejected.
- Rule-complexity limits and C-API misuse (NULL pointers, double-free, bad struct sizes, NaN/Infinity) — return proper error codes.
- Locale independence — evaluation does not use locale, timezone, or wall-clock as inputs (determinism contract, DET-002); cross-locale equivalence is exercised in CI.
- Concurrency — the engine uses a per-thread compiler model; concurrent and long-running (soak) execution is exercised on every release in CI under AddressSanitizer/UndefinedBehaviorSanitizer. A compiler shared across threads is rejected at runtime with `AX_ERR_CONCURRENT_COMPILER_USE` rather than corrupting state.

**Performance shape.** Evaluation is in-process — no network hop, no serialization — and bytecode
evaluation avoids parsing on the hot path. Throughput scales with per-thread compilers; measure on
your target hardware and workload.

## Proven determinism

"Same input, same decision" is a published, recomputable proof — not a slogan. On every release the same bytecode is evaluated on **real Linux and real Windows** (x86_64), the decision output is serialized and hashed, and the two platforms' hashes are byte-identical. The evidence lives in this repository, so you can verify it yourself:

- Cross-platform comparison reports (Windows-x64 vs Linux-x64) — [`reports/determinism_compare_v1/2026-07-11/`](reports/determinism_compare_v1/2026-07-11/) — each `status: pass`, every hash byte-identical (e.g. [the DET-001 comparison](reports/determinism_compare_v1/2026-07-11/DET-001/windows-x64__linux-x64/comparison.json)). This set was produced by the **v1.0.2 engine** — the same binaries you can download and run — and its hashes are identical to the earlier published sets (`2026-06-21`, `2026-06-23`), which remain committed as history.
- Each bundle ships the raw `output.bin`, inputs, options, and a `SHA256SUMS.txt` — recompute the hashes and compare the two platforms yourself.
- Cross-machine (same-platform) reproduction — a fresh Windows-x64 desktop, running the shipped v1.0.2 binaries, reproduced the published DET-001/DET-003 golden hashes byte-for-byte: [`reports/cross_machine_replay_v1/2026-07-14/`](reports/cross_machine_replay_v1/2026-07-14/). One operator, two machines; broader multi-host and independent third-party reproduction remain open.

Determinism is enforced at build time (fast-math is rejected) and gated in CI: the cross-platform comparison fails the release if any hash diverges.

## Why RuleDSL (vs other rule engines)

Most rule engines evaluate rules; RuleDSL is built so you can **prove and audit** the result.

- **Deterministic — and proven.** Same input → byte-identical decision on Linux and Windows, with the cross-platform hashes committed in this repo (see [Proven determinism](#proven-determinism)). Many engines are deterministic in practice; few publish the proof.
- **In-process, no runtime baggage.** A C ABI library (`.so` / `.dll`) — no JVM, no daemon, no network hop, no policy sidecar. Embeds directly in C, C++, Python, or C# (Drools requires a JVM; OPA/Rego typically runs as a separate service).
- **Auditable and honest.** Compact, integrity-checked bytecode, a published error contract, and a conformance status documenting exactly what the engine does versus the spec (see [Language version & conformance](#language-version--conformance)) — instead of claiming more than it ships.

Performance is deliberately not the headline: evaluation is in-process and parse-free on the hot path, but measure throughput on your own hardware — we don't publish cherry-picked numbers.

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
| Python 3.7+ | [`bindings/python/`](bindings/python/README.md) or `pip install ruledsl` | None (pure ctypes) |
| C# (.NET 6+) | [`bindings/csharp/`](bindings/csharp/README.md) | None (P/Invoke) |

The [`ruledsl`](https://pypi.org/project/ruledsl/) package on PyPI carries the
Python binding plus the desktop **workbench** (authoring & replay companion) as
the `ruledsl-workbench` command. It is pure Python — the engine library itself
still comes from [Releases](https://github.com/axiom-foundry/RuleDSL-SDK/releases):

```sh
pip install ruledsl
ruledsl-workbench --dll path/to/bundle/bin/ruledsl_capi.dll
```

## Documentation

| Topic | Document |
|-------|----------|
| **Rule cookbook** | [`docs/rule_cookbook.md`](docs/rule_cookbook.md) |
| Error handling | [`docs/errors.md`](docs/errors.md) |
| Troubleshooting | [`docs/troubleshooting.md`](docs/troubleshooting.md) |
| Integration snippets | [`docs/integration_snippets.md`](docs/integration_snippets.md) |

Full documentation index: [`docs/README.md`](docs/README.md)
