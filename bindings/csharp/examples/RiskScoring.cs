// Risk Scoring Example — RuleDSL C# Binding
//
// Usage:
//   dotnet run
//
// Ensure ruledsl_capi.dll is in the application directory or PATH.

using System;
using System.Collections.Generic;
using Axiom.RuleDSL;

class Program
{
    static void Main()
    {
        using var engine = new RuleDSLEngine();
        Console.WriteLine($"Engine version: {engine.Version()}");

        // Compile risk scoring rules
        var bytecode = engine.Compile(@"
            rule high_risk_transaction {
                when amount > 1000 and currency == ""USD"";
                then decline;
            }

            rule medium_risk_transaction {
                when amount > 500;
                then review;
            }

            rule default_allow {
                when amount > 0;
                then allow;
            }
        ");
        Console.WriteLine($"Compiled successfully ({bytecode.Length} bytes)");

        // Test transactions
        var transactions = new[]
        {
            new Dictionary<string, object> { { "amount", 1200.0 }, { "currency", "USD" } },
            new Dictionary<string, object> { { "amount", 800.0 },  { "currency", "EUR" } },
            new Dictionary<string, object> { { "amount", 50.0 },   { "currency", "USD" } },
        };

        Console.WriteLine("\n--- Evaluating transactions ---");
        for (int i = 0; i < transactions.Length; i++)
        {
            try
            {
                var decision = engine.Evaluate(bytecode, transactions[i]);
                Console.WriteLine($"TX {i + 1}: amount={transactions[i]["amount"]} " +
                    $"{transactions[i]["currency"]} -> {decision.Action} " +
                    $"(rule: {decision.RuleName ?? "none"})");
            }
            catch (EvalException ex)
            {
                Console.WriteLine($"TX {i + 1}: ERROR {ex.Code}: {ex.Message}");
            }
        }
    }
}
