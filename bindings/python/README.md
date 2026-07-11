# RuleDSL Python Binding

Pure Python (ctypes) wrapper for the RuleDSL C API. No compilation needed — just point it at your `ruledsl_capi.dll` or `libruledsl_capi.so`.

## Install

Three equivalent ways to get the binding (+ workbench):

```sh
pip install ruledsl          # from PyPI; adds the `ruledsl-workbench` command
```

…or use the files in this folder directly (they ship inside the SDK bundle's
`bindings/python/`, and newer bundles include `workbench.py` too). The package
is pure Python; the **engine library is not inside** — it comes from
[Releases](https://github.com/axiom-foundry/RuleDSL-SDK/releases).

## Requirements

- Python 3.7+
- RuleDSL shared library (`ruledsl_capi.dll` on Windows, `libruledsl_capi.so` on Linux)
- No third-party dependencies

## Quick Start

```python
from ruledsl import RuleDSL

# Initialize (pass path to your shared library)
engine = RuleDSL("path/to/ruledsl_capi.dll")

# Compile a rule
bytecode = engine.compile("""
    rule high_risk {
        when amount > 1000 and currency == "USD";
        then risk_score = 95, reason = "high_value_usd", decline;
    }
""")

# Evaluate
decision = engine.evaluate(bytecode, {
    "amount": 1200.0,
    "currency": "USD",
})

print(decision.matched)     # True
print(decision.action)      # "DECLINE"
print(decision.rule_name)   # "high_risk"
print(decision.outputs)     # {"reason": "high_value_usd", "risk_score": 95.0}

# Clean up
engine.close()
```

## Context Manager

```python
with RuleDSL("ruledsl_capi.dll") as engine:
    bc = engine.compile('rule r1 { when x > 10; then review; }')
    result = engine.evaluate(bc, {"x": 15.0})
    print(result)  # Decision(matched=True, action='REVIEW')
```

## Priority and LIMIT

Rules support priority ordering and rate-limit actions:

```python
bytecode = engine.compile("""
    rule high_risk priority 10 {
        when amount > 5000;
        then decline;
    }
    rule spending_cap priority 5 {
        when amount > 500;
        then limit 1000 USD per 1 d;
    }
""")
```

Priority goes between the rule name and opening brace. Higher priority is evaluated first.
Time units: `s` (second), `m` (minute), `h` (hour), `d` (day) — case-insensitive.

## Field Types

| Python type | RuleDSL type | Example |
|-------------|-------------|---------|
| `float` / `int` | NUMBER | `{"amount": 1200.0}` |
| `str` | STRING | `{"currency": "USD"}` |
| `bool` | BOOL | `{"is_vip": True}` |
| `None` | MISSING | `{"country": None}` |

## Time

Time-based rules require `now_utc_ms` (epoch milliseconds). It must be supplied
**explicitly** — neither the engine nor this wrapper ever reads the system clock,
because a deterministic engine must be a pure function of explicit inputs. Omitting
it for a time-based rule raises `EvalError` (`MISSING_NOW_UTC_MS`).

```python
# Supply the time from your host application's clock at the call site:
decision = engine.evaluate(bytecode, {"amount": 100.0}, now_utc_ms=1700000000000.0)

# ...or pass it as an explicit field:
decision = engine.evaluate(bytecode, {"amount": 100.0, "now_utc_ms": 1700000000000.0})
```

## Bytecode I/O

```python
# Save compiled bytecode
bytecode = engine.compile(rule_source)
bytecode.save("rules.axbc")

# Load bytecode from file
from ruledsl import Bytecode
bytecode = Bytecode.from_file("rules.axbc")
```

## Compatibility Check

```python
info = engine.check_compatibility(bytecode)
print(info["compatible"])      # True
print(info["axbc_version"])    # 3
print(info["lang_major"])      # 0   (v1.0 bytecode carries the internal language tag 0.9)
print(info["lang_minor"])      # 9
```

## Output Fields

Rules can assign output fields in the `then` clause. These are available in `decision.outputs` as a dict:

```python
bytecode = engine.compile("""
    rule fraud_check {
        when amount > 5000 and ip_country in [NG, RU];
        then risk_score = 95, reason = "multi_signal", decline;
    }
""")

decision = engine.evaluate(bytecode, {
    "amount": 7500.0,
    "ip_country": "NG",
})

print(decision.outputs["risk_score"])  # 95.0
print(decision.outputs["reason"])      # "multi_signal"
```

Output field values are typed: numbers return as `float`, strings as `str`, booleans as `bool`.
If no rule matches or the matching rule has no assignments, `outputs` is an empty dict.

## Decision Behavior

When a rule matches, `decision.matched` is `True` and `decision.action` reflects the matched rule's action.
When no rule matches, `decision.matched` is `False`, `decision.outputs` is empty, and the `action` field should not be relied upon.

Always check `decision.matched` before reading `decision.action`.

## Error Handling

```python
from ruledsl import RuleDSL, CompileError, EvalError, RuleDSLError

engine = RuleDSL("ruledsl_capi.dll")

# Compile errors
try:
    engine.compile("invalid rule text")
except CompileError as e:
    print(f"Compile failed: {e}")
    print(f"Error code: {e.code}")

# Eval errors
try:
    result = engine.evaluate(bytecode, {"amount": float("nan")})
except EvalError as e:
    print(f"Eval failed: {e.code_name}")  # "AX_ERR_NON_FINITE"
```

## Thread Safety

Each `RuleDSL` instance uses an internal lock to serialize `compile()` and `evaluate()` calls. Multiple threads can safely share a single instance — the lock prevents concurrent access to the underlying C compiler state.

For maximum throughput, create one `RuleDSL` instance per thread to avoid lock contention.

## Evaluation Trace

`evaluate()` accepts an optional `on_trace` callable. The engine invokes it once
per action assignment, per decision, and per runtime error — the "why" behind a
decision (`AXTraceCallback` in the C API):

```python
trace = []
decision = engine.evaluate(bytecode, {"amount": 2500.0},
                           now_utc_ms=1700000000000.0,
                           on_trace=trace.append)
print("\n".join(trace))
# Set reason = "hourly_cap"
# Set risk_score = 25
# Decision = LIMIT 10000 USD PER 1 H
```

An exception raised inside `on_trace` never crosses the C boundary — it is
caught and re-raised after evaluation completes.

## Workbench (GUI) — authoring & replay companion

`workbench.py` is a zero-dependency Tkinter desktop tool for the two human ends
of the rule pipeline. It is not a server component: production rulesets are
compiled by `ruledslc` and evaluated in-process by your server via the C ABI.

**Authoring** — a rule editor with three ready scenarios (from the shipped
`examples/`), `File > Open Rules… / Save Rules As…` for real `.rule` files, an
input panel, the decision with its output fields and evaluation trace, a
canonical decision hash (the `replay_proof_producer.py` convention), and a
"Run 100×" button that demonstrates the determinism contract live — every run
must produce the identical decision hash.

**Replay** — `File > Open Bytecode (Replay)…` loads a compiled `.axbc` exactly
as the server ran it (no recompilation; the rules editor is disabled and the
bytecode's SHA-256 is shown), and `File > Load Inputs from JSON…` restores an
incident's inputs (flat fields dict, or `{"fields": …, "now_utc_ms": …}`).
Same bytecode, same input → the same decision and trace, on your desk.

**Cases** — `File > Open Cases (JSON / JSONL)…` runs many inputs against the
current ruleset (or the loaded bytecode in replay mode) and lists one decision
per row: action, matched rule, outputs, and decision-hash prefix, with a
per-action summary. Double-click a row to inspect that case in Result/Trace.
Each case may carry its own `now_utc_ms`; otherwise the panel clock applies.

**Explicit clock, humane input** — the clock field accepts epoch milliseconds
*or* ISO-8601 (`2023-11-14T22:13:20Z`), translates between the two live, and a
**Now (UTC)** button stamps the current time on explicit click. Empty still
means omitted: the engine never reads the system clock, so time-based rules
without a clock raise the deterministic `MISSING_NOW_UTC_MS` error.

The workbench deliberately does **not** export `.axbc`: production artifacts
come from `ruledslc`, which stamps the authenticity manifest.

```sh
python workbench.py                      # bundle layout: finds ../../bin automatically
python workbench.py --dll path/to/ruledsl_capi.dll
```

Requires a standard CPython install (Tkinter ships with it). No third-party
dependencies.

## Engine Version

```python
print(engine.version())  # "RuleDSL/1.0.2 (abi=1)"
```
