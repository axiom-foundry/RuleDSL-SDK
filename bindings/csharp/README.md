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
        then decline;
    }
");

var decision = engine.Evaluate(bytecode, new Dictionary<string, object>
{
    { "amount", 1200.0 },
    { "currency", "USD" },
});

Console.WriteLine(decision.Action);    // "DECLINE"
Console.WriteLine(decision.Matched);   // True
Console.WriteLine(decision.RuleName);  // "high_risk"
```

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
