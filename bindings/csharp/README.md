# RuleDSL C# Binding

P/Invoke wrapper for the RuleDSL C API. Single-file, no NuGet dependencies.

## Requirements

- .NET 6+ or .NET Framework 4.7.2+
- RuleDSL shared library (`ruledsl_capi.dll` on Windows, `libruledsl_capi.so` on Linux) in the application directory or system PATH

## Quick Start

```csharp
using Axiom.RuleDSL;

using var engine = new RuleDSLEngine();

var bytecode = engine.Compile(@"
    rule high_risk {
        when amount > 1000 and currency == ""USD"";
        then risk_score = 95, reason = ""high_value_usd"", decline;
    }
");

var decision = engine.Evaluate(bytecode, new Dictionary<string, object>
{
    { "amount", 1200.0 },
    { "currency", "USD" },
});

Console.WriteLine(decision.Action);                  // "DECLINE"
Console.WriteLine(decision.Matched);                 // True
Console.WriteLine(decision.RuleName);                // "high_risk"
Console.WriteLine(decision.Outputs["risk_score"]);   // 95
Console.WriteLine(decision.Outputs["reason"]);       // "high_value_usd"
```

## Priority and LIMIT

Rules support priority ordering and rate-limit actions:

```csharp
var bytecode = engine.Compile(@"
    rule high_risk priority 10 {
        when amount > 5000;
        then decline;
    }
    rule spending_cap priority 5 {
        when amount > 500;
        then limit 1000 USD per 1 d;
    }
");
```

Priority goes between the rule name and opening brace. Higher priority is evaluated first.
Time units: `s` (second), `m` (minute), `h` (hour), `d` (day) — case-insensitive.

## Field Types

| C# type | RuleDSL type | Example |
|---------|-------------|---------|
| `double` / `int` / `long` / `float` | NUMBER | `{"amount", 1200.0}` |
| `string` | STRING | `{"currency", "USD"}` |
| `bool` | BOOL | `{"is_vip", true}` |
| `null` | MISSING | `{"country", null}` |

## Time Injection

```csharp
// Automatic (uses DateTimeOffset.UtcNow)
var decision = engine.Evaluate(bytecode, fields);

// Manual (for deterministic replay)
var decision = engine.Evaluate(bytecode, fields, nowUtcMs: 1700000000000.0);
```

## Bytecode I/O

```csharp
// Save
var bytecode = engine.Compile(ruleSource);
bytecode.Save("rules.axbc");

// Load
var bytecode = Bytecode.FromFile("rules.axbc");
```

## Output Fields

Rules can assign output fields in the `then` clause. These are available via `decision.Outputs`:

```csharp
var bytecode = engine.Compile(@"
    rule fraud_check {
        when amount > 5000 and ip_country in [NG, RU];
        then risk_score = 95, reason = ""multi_signal"", decline;
    }
");

var decision = engine.Evaluate(bytecode, new Dictionary<string, object>
{
    { "amount", 7500.0 },
    { "ip_country", "NG" },
});

Console.WriteLine(decision.Outputs["risk_score"]);  // 95
Console.WriteLine(decision.Outputs["reason"]);      // "multi_signal"
```

Output field values are typed: numbers as `double`, strings as `string`, booleans as `bool`.
`Outputs` is `IReadOnlyDictionary<string, object?>` — empty when no rule matches or no assignments exist.

## Decision Behavior

When a rule matches, `decision.Matched` is `true` and `decision.Action` reflects the matched rule's action.
When no rule matches, `decision.Matched` is `false`, `decision.Outputs` is empty, and the `Action` property should not be relied upon.

Always check `decision.Matched` before reading `decision.Action`.

## Error Handling

```csharp
try
{
    var bc = engine.Compile("invalid rule");
}
catch (CompileException ex)
{
    Console.WriteLine($"Code: {ex.Code}");     // Compile
    Console.WriteLine($"Detail: {ex.Detail}");
}

try
{
    var result = engine.Evaluate(bytecode, fields);
}
catch (EvalException ex)
{
    Console.WriteLine($"Code: {ex.Code}");     // e.g., NonFinite
    Console.WriteLine($"Detail: {ex.Detail}");
}
```

## Running the Example

```
cd bindings/csharp/examples
# Copy ruledsl_capi.dll into the examples directory, then:
dotnet run
```

## Library Resolution

The binding expects `ruledsl_capi` to be resolvable by the .NET runtime:

- **Windows**: Place `ruledsl_capi.dll` next to your executable or in PATH
- **Linux**: Place `libruledsl_capi.so` in `LD_LIBRARY_PATH` or `/usr/local/lib`

For custom paths, use `NativeLibrary.SetDllImportResolver` (.NET 6+):

```csharp
NativeLibrary.SetDllImportResolver(typeof(RuleDSLEngine).Assembly,
    (name, assembly, path) =>
    {
        if (name == "ruledsl_capi")
            return NativeLibrary.Load("/custom/path/ruledsl_capi.dll");
        return IntPtr.Zero;
    });
```

## Thread Safety

Each `RuleDSLEngine` instance is single-threaded. For concurrent use, create one instance per thread or use a pool pattern.
