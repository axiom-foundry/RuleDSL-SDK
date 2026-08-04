# RuleDSL SDK (C API)

RuleDSL is infrastructure for **executable business policies**: a deterministic rule-evaluation engine embedded through a stable public C ABI design. See the [product overview and live demos](https://axiom-foundry.github.io/RuleDSL-SDK/).
Published v1.0.2 evidence verifies byte-identical decisions on Windows x86_64 and Linux x86_64 when the engine/ABI, bytecode, canonical input, and evaluation options match.

**Linux & Windows x86_64 · engine/binary bundle v1.0.2 · language implementation v0.9 (v1.0 = target spec) · Python package 1.2.0 · MCP package surface 0.2.0.**

The PyPI 1.2.0 artifacts were built from source commit
`837ae3062d666c5e3ef0711966eb8f95605412e5`. This documentation records that
published state; the engine binary remains the separate v1.0.2 bundle.

**Use cases**: transaction risk scoring, host-enforced spending-limit evaluation, compliance gating, offer eligibility, real-time policy evaluation, **and a deterministic decision layer for AI agents (via MCP)**.

**What it is**: a core in-process engine library (`.dll` / `.so`) with no daemon, network service, database, or sidecar. The Python binding loads that separate engine library, the Workbench uses Tk, and the MCP extra requires Python 3.10+ plus the MCP SDK.

**What it is not**: not a SaaS, not an open-source engine, not a 24/7 managed service.

**Open vs closed.** This repository is the **SDK** — headers, language bindings, examples, documentation, and determinism evidence, source-available for integration. The **engine** ships as a licensed binary in [Releases](https://github.com/axiom-foundry/RuleDSL-SDK/releases), not as open source. See [`LICENSE`](LICENSE) and [`EVALUATION_TERMS.md`](EVALUATION_TERMS.md).

> **Get started:** Download the latest bundle from [Releases](https://github.com/axiom-foundry/RuleDSL-SDK/releases). The bundle includes the engine library, compiler, headers, language bindings, and documentation — everything you need to integrate.
>
> **See it before you integrate:** the [demos](https://axiom-foundry.github.io/RuleDSL-SDK/demos/) show the engine running live, and `pip install ruledsl` adds the desktop **workbench** (`ruledsl-workbench`) — author rules interactively, read the engine's decision trace, and replay production `.axbc` bytecode on your desk. Pure Python; the engine itself still comes from the v1.0.2 bundle. **MCP early access:** `pip install "ruledsl[mcp]"` installs the current 1.2.0 Python package and MCP 0.2.0 surface. The [MCP quickstart](docs/mcp_quickstart.md) also keeps a checkout/PYTHONPATH route for development and source inspection.

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

The Quickstart compiles with `--lang 0.9`. The shipped engine implements **language version v0.9** — the honest, deterministic subset of the **v1.0** target specification. The v1.0 spec is the normative target; known divergences in the shipped v0.9 behavior are documented here:

- **Shipped behavior, and where it diverges from the v1.0 target** — [`docs/language/conformance_status_v0_9.md`](docs/language/conformance_status_v0_9.md)
- **The v1.0 target specification** — [`docs/language/spec_v1_0.md`](docs/language/spec_v1_0.md)

## Engine Robustness

The RuleDSL parser and verified bytecode-loading paths return structured errors for supported,
detected failures. Detection coverage is not a blanket safety guarantee: passing malformed or
truncated bytecode directly to evaluation, invalid pointers/sizes/ownership/lifetimes, or violating
threading rules can be undefined behavior. See the [undefined-behavior boundaries](docs/contracts/undefined_behavior_v1_0.md)
and [thread-safety model](docs/thread_safety_model.md).

**Internal release qualification.** Private engine CI exercises the parser and bytecode loader with
coverage-guided fuzzing (libFuzzer under AddressSanitizer + UndefinedBehaviorSanitizer), seeded with an
adversarial corpus maintained in the engine repository. This public SDK repository does not publish
the engine source or every internal run, so this is vendor-reported release qualification rather than
independently reproducible public evidence.

**Qualification scenarios include:**

- Malformed rule sources and supported tampered-bytecode detection paths (flipped bits, truncated files, wrong magic, oversized payloads) are exercised by the adversarial corpus. Verify integrity and compatibility before evaluation; direct evaluation of malformed bytecode is outside the contract.
- SQL, markup, and CRLF content is ordinary string data when it satisfies the documented encoding, schema, type, and size contract. Rejection claims apply to violations such as invalid encoding, NUL, schema/type mismatch, and configured limits — not to those strings merely because of their content.
- Rule-complexity limits, NULLs, documented size checks, and NaN/Infinity exercise supported error paths. Invalid pointers, ownership/lifetime violations, and double-free are not promised detection paths.
- Locale independence — evaluation does not use locale, timezone, or wall-clock as inputs (determinism contract, DET-002); cross-locale checks are part of internal engine qualification. Public determinism evidence is limited to the committed DET corpus below.
- Concurrency — two live calls on the same compiler can be detected and return `AX_ERR_CONCURRENT_COMPILER_USE`; destroying a compiler while a call is running is undefined behavior in the raw C API. The shipped Python and C# wrappers serialize native calls and protect `close()`/`Dispose()`. Concurrent and long-running soak checks under AddressSanitizer/UndefinedBehaviorSanitizer are internal engine release qualification, not independently visible runs in this public repository.

**Performance shape.** Evaluation is in-process — no network hop, no serialization — and bytecode
evaluation avoids parsing on the hot path. Throughput scales with per-thread compilers; measure on
your target hardware and workload.

## Published determinism evidence

For the published DET corpus and scenarios, the shipped v1.0.2 Windows x86_64 and Linux x86_64 binaries produced bit-identical decision output under the same engine/ABI, bytecode, canonical input, and equivalent options. The committed artifacts make those observations recomputable. They are not a formal proof over every possible rule and input.

- Cross-platform comparison reports (Windows-x64 vs Linux-x64) — [`reports/determinism_compare_v1/2026-07-11/`](reports/determinism_compare_v1/2026-07-11/) — each `status: pass`, every hash byte-identical (e.g. [the DET-001 comparison](reports/determinism_compare_v1/2026-07-11/DET-001/windows-x64__linux-x64/comparison.json)). This set was produced by the **v1.0.2 engine** — the same binaries you can download and run — and its hashes are identical to the earlier published sets (`2026-06-21`, `2026-06-23`), which remain committed as history.
- Each bundle ships the raw `output.bin`, inputs, options, and a `SHA256SUMS.txt` — recompute the hashes and compare the two platforms yourself.
- Cross-machine (same-platform) reproduction — a fresh Windows-x64 desktop, running the shipped v1.0.2 binaries, reproduced the published DET-001/DET-003 golden hashes byte-for-byte: [`reports/cross_machine_replay_v1/2026-07-14/`](reports/cross_machine_replay_v1/2026-07-14/). One operator, two machines; broader multi-host and independent third-party reproduction remain open.

The build contract rejects fast-math. The committed comparison reports and raw bundle files let readers recompute the published corpus results and inspect any hash divergence directly.

## AI agents (MCP) — early access

AI agents are getting real work in regulated flows. The question is never whether the model is smart — it's whether the decision can be **replayed**. RuleDSL's answer ships as the MCP 0.2.0 early-access server: **the agent invokes; the engine decides.** The agent still chooses a declared rule and extracts the fields; a wrong rule or wrong field extraction is outside the engine's determinism guarantee.

- **Three tools, closed surface:** `list_rules` · `evaluate_case` · `engine_info`. There is deliberately no `decide`, no `write_rule`, no free-text compile — an agent can invoke decision logic, never alter it.
- **Successful evaluations can leave replay evidence:** with `--decision-log` enabled, each successful `evaluate_case` writes a canonical decision record containing `rule_sha256`, `bytecode_sha256`, and `decision_hash`. The `decision_hash` covers only the canonical decision payload; there is no whole-record hash or hash chain. Failed calls return typed errors and write no decision record. This file is evidence for recomputation, not an audit ledger or system of record.
- **Install today:** `pip install "ruledsl[mcp]"` installs Python package 1.2.0 and the MCP 0.2.0 surface. Setup, including Claude Desktop config and the developer/source checkout alternative: [docs/mcp_quickstart.md](docs/mcp_quickstart.md). The engine library still comes from the v1.0.2 release bundle.

Early access: the tool surface may still evolve before it joins the frozen compatibility contract.

## Why RuleDSL (vs other rule engines)

Most rule engines evaluate rules; RuleDSL is built to provide **recomputable decision evidence for technical review**.

- **Published determinism evidence.** Matching engine/ABI, bytecode, canonical input, and options produced byte-identical decisions for the committed DET corpus on the shipped Linux and Windows x86_64 binaries (see [Published determinism evidence](#published-determinism-evidence)).
- **In-process core engine.** The C ABI library (`.so` / `.dll`) needs no JVM, daemon, network hop, database, or policy sidecar. Bindings and tools retain their documented runtime requirements.
- **Reviewable and honest.** Compact, integrity-checked bytecode, a published error contract, recomputable decision evidence, and a conformance status document exactly what the engine does versus the spec (see [Language version & conformance](#language-version--conformance)).

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
| Python 3.7+ | [`bindings/python/`](bindings/python/README.md) or `pip install ruledsl` | separate engine `.dll`/`.so`; the binding uses stdlib `ctypes`; the Workbench also requires Tk |
| Python 3.10+ | [`pip install "ruledsl[mcp]"`](docs/mcp_quickstart.md) for the published 1.2.0 package; checkout/PYTHONPATH remains a developer/source alternative | separate engine `.dll`/`.so` plus the official `mcp` SDK; the range is `>=2.0,<3`, and CI verifies every version it claims (today: `2.0.0`, the only 2.x release, with its transitive closure pinned). 3.10 is that SDK's floor, not ours |
| C# (.NET 6+) | [`bindings/csharp/`](bindings/csharp/README.md) | separate engine `.dll`/`.so`; the wrapper uses P/Invoke. CI builds **and runs** the suite on `net6.0` and `net8.0` |

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
| MCP server quickstart (early access) | [`docs/mcp_quickstart.md`](docs/mcp_quickstart.md) |
| Purchase-approval MCP shadow pilot | [`examples/mcp_pilot/`](examples/mcp_pilot/) |
| MCP design contract | [`docs/design/mcp_server_v0.md`](docs/design/mcp_server_v0.md) |

Full documentation index: [`docs/README.md`](docs/README.md)
