# ruledsl

Python binding and desktop **workbench** for [RuleDSL](https://axiom-foundry.github.io/RuleDSL-SDK/) —
a deterministic, embedded business-rule engine with a stable C ABI.
*Same input, same bytecode, same decision — on every run and every platform.*

This package is **pure Python** (ctypes, zero dependencies). The engine library
itself (`ruledsl_capi.dll` / `libruledsl_capi.so`) is **not** inside — download an
SDK bundle from [GitHub Releases](https://github.com/axiom-foundry/RuleDSL-SDK/releases)
and point the binding at it.

## The workbench — authoring & replay companion

```sh
pip install ruledsl
ruledsl-workbench --dll path/to/ruledsl_capi.dll
```

A zero-dependency Tkinter desktop tool for the two human ends of the rule
pipeline (it is not a server component — servers embed the C ABI directly):

- **Authoring:** edit a ruleset (or `File > Open Rules…`), run it against sample
  inputs, read the decision, its output fields, the engine's own evaluation
  trace (*why* this decision), and a canonical decision hash. **Run 100×**
  asserts every run produced the identical hash — the determinism contract, live.
- **Replay:** `File > Open Bytecode (Replay)…` loads a compiled `.axbc` exactly
  as your server ran it (no recompilation; the editor is disabled), and
  `File > Load Inputs from JSON…` restores an incident's inputs. Same bytecode,
  same input → the same decision and trace, on your desk.
- Deliberately **no** `.axbc` export: production artifacts come from `ruledslc`,
  which stamps the authenticity manifest.

## The binding

```python
from ruledsl import RuleDSL

with RuleDSL("path/to/ruledsl_capi.dll") as engine:   # .so on Linux
    bytecode = engine.compile('rule r1 { when amount > 100; then decline; }')
    decision = engine.evaluate(bytecode, {"amount": 250.0})
    print(decision.action, decision.rule_name)         # DECLINE r1

    trace = []
    engine.evaluate(bytecode, {"amount": 250.0}, on_trace=trace.append)
    print("\n".join(trace))                            # why this decision
```

Deterministic by contract: the engine never reads the system clock (time-based
rules require an explicit `now_utc_ms`), never touches the network, and returns
stable, append-only error codes.

## The MCP server — optional `[mcp]` extra (EXPERIMENTAL)

```sh
pip install "ruledsl[mcp]"
ruledsl-mcp --rules path/to/rules --decision-log decisions.jsonl --engine-lib path/to/libruledsl_capi.so
```

An MCP (Model Context Protocol) stdio server that lets an AI agent *invoke*
deterministic rule evaluation — never *produce* the decision itself. Exactly
three tools (`list_rules`, `evaluate_case`, `engine_info`), a hash-verified
rule-library manifest, a mandatory explicit `now_utc_ms` (the server never
reads a clock), and a canonical JSONL decision log with a replayable
`decision_hash` per decision. Requires Python 3.10+; setup and Claude Desktop
configuration:
[MCP quickstart](https://github.com/axiom-foundry/RuleDSL-SDK/blob/main/docs/mcp_quickstart.md).

## Changelog

- **1.2.0** — MCP contract stabilization. The experimental MCP surface gets a
  strict, published contract: per-rule input schemas, typed errors carried as
  `isError`, matching value fidelity in the Python and C# bindings, and CI that
  holds all of it. **This breaks callers on purpose** — see the migration notes
  below. The engine, the language, and the decision payload are unchanged.
- **1.1.1** — self-contained pip path for MCP: the example rule library ships
  inside the wheel (`ruledsl-mcp --print-example-rules`), the smoke client is
  a module (`python -m ruledsl_mcp.smoke`, no checkout needed), a clear
  Python 3.10+ runtime message, and `serverInfo.version` reports the package.
- **1.1.0** — MCP server migrated into the package as the optional
  `[mcp]` extra + `ruledsl-mcp` console command (EXPERIMENTAL). Base
  package unchanged and still zero-dependency.
- **1.0.3** — workbench: Cases batch runner (JSON/JSONL) + humane explicit
  clock (ISO-8601 ⇄ epoch-ms echo, Now (UTC) button).
- **1.0.2** — first public release: binding (`on_trace`, cached buffers) +
  workbench (authoring, replay, JSON inputs).

## Migrating to 1.2.0

Everything below is a deliberate break. The MCP surface is EXPERIMENTAL and had
no compatibility promise; keeping the old paths alive would have meant shipping
two contracts, one of which quietly produced wrong answers.

| What changed | What to do |
|---|---|
| Rule libraries must declare `manifest_version: 2`, and every rule must carry an `input_schema`. A v1 manifest is refused at startup. | Add `"manifest_version": 2` and an `input_schema` per rule. Call `list_rules` — it returns each rule's schema. |
| Failed tool calls now return `CallToolResult(isError=true)` with a structured `{error_domain, error_code, error_name, message, field}` object. They used to look like successes. | Branch on `isError` / `error_code` instead of parsing text. |
| `now_utc_ms` must be a JSON **integer**, at or after the epoch. A numeric string, a fractional value and a negative value are all refused; an integral float normalizes to the same integer. | Send an integer. |
| Integers outside ±(2^53−1) are refused instead of being silently rounded. This is the one break that reaches non-MCP binding users. | Pass identifiers (account numbers, ledger ids) as **strings**. They were never safe as numbers — a float64 cannot hold them, so the engine was already evaluating a different value than you sent. |
| Fields the rule's schema does not declare are refused, not ignored. Strings containing NUL, text with no UTF-8 form, and non-scalar values are refused. | Match the declared schema exactly. |
| The `mcp` SDK 1.x / FastMCP path is gone; the extra requires `mcp>=2.0,<3`. | `pip install -U "ruledsl[mcp]"`. |

If you supply `now_utc_ms` both as an argument and as a `now_utc_ms` field, that
is now an error rather than the argument silently winning.

## Version & license

Package `1.x` targets engine `1.0.x` (ABI 1); the minor version moves when the
package itself gains capability (e.g. `1.1.0` added the `[mcp]` extra).
Licensed under the **PolyForm Free Trial License 1.0.0** — evaluation use;
commercial production use requires a separate agreement (see the
[repository](https://github.com/axiom-foundry/RuleDSL-SDK)).
