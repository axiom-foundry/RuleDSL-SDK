# RuleDSL Python Binding

Pure Python (ctypes) wrapper for the RuleDSL C API. No compilation needed — just point it at your `ruledsl_capi.dll` or `libruledsl_capi.so`.

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
        then decline;
    }
""")

# Evaluate
decision = engine.evaluate(bytecode, {
    "amount": 1200.0,
    "currency": "USD",
})

print(decision.matched)   # True
print(decision.action)    # "DECLINE"

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

## Field Types

| Python type | RuleDSL type | Example |
|-------------|-------------|---------|
| `float` / `int` | NUMBER | `{"amount": 1200.0}` |
| `str` | STRING | `{"currency": "USD"}` |
| `bool` | BOOL | `{"is_vip": True}` |
| `None` | MISSING | `{"country": None}` |

## Time Injection

The engine requires `now_utc_ms` for time-based rules. The wrapper auto-injects it from the system clock if not provided:

```python
# Automatic (uses current time)
decision = engine.evaluate(bytecode, {"amount": 100.0})

# Manual (for deterministic replay)
decision = engine.evaluate(bytecode, {"amount": 100.0}, now_utc_ms=1700000000000.0)
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
print(info["lang_major"])      # 1
```

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

## Engine Version

```python
print(engine.version())  # "RuleDSL/1.0.0 (abi=1)"
```
