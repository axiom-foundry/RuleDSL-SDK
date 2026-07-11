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

## Version & license

Package versions track the SDK line (`1.0.x` works with engine `1.0.x`, ABI 1).
Licensed under the **PolyForm Free Trial License 1.0.0** — evaluation use;
commercial production use requires a separate agreement (see the
[repository](https://github.com/axiom-foundry/RuleDSL-SDK)).
