// RuleDSL C# binding lifecycle and value-fidelity tests.
//
// Mirrors tests/mcp/test_binding_lifecycle.py. Two properties, both invisible
// to a single-threaded happy path:
//
//   1. Lifetime. Destroying the compiler while another thread is inside a
//      native call is a use-after-free. It does not fail loudly: the observed
//      signature on the Python side was a "successful" decision whose output
//      fields were silently empty. Dispose() must wait, and every outcome must
//      be either a correct Decision or ObjectDisposedException.
//
//   2. Value fidelity. A value that reaches the engine altered (NUL-truncated
//      string, integer rounded past 2^53) makes the binding report an input
//      the engine never evaluated. Those are rejected, not adjusted.
//
// Self-running, no test framework: exit code 0 = pass, 1 = failure, matching
// the repository's Python suites.
//
// Engine location: RULEDSL_DLL (absolute path to ruledsl_capi.dll / .so).

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using Axiom.RuleDSL;

internal static class Program
{
    private static int _passed;
    private static int _failed;

    private const long NowUtcMs = 1700000000000L;

    private static string RuleSource = "";

    private static readonly Dictionary<string, object?> ExtremeOutputs = new()
    {
        { "reason", "extreme_amount" },
        { "risk_score", 99.0 },
    };

    private static int Main()
    {
        string dll = Environment.GetEnvironmentVariable("RULEDSL_DLL") ?? "";
        if (string.IsNullOrEmpty(dll) || !File.Exists(dll))
        {
            Console.Error.WriteLine(
                "RULEDSL_DLL must point at the engine library (ruledsl_capi.dll / .so). " +
                $"Got: '{dll}'");
            return 2;
        }

        // Resolve ruledsl_capi to the explicit path instead of relying on PATH
        // or the output directory, so the test binds the engine the caller
        // named and nothing else.
        NativeLibrary.SetDllImportResolver(
            Assembly.GetExecutingAssembly(),
            (name, asm, path) => name == "ruledsl_capi" ? NativeLibrary.Load(dll) : IntPtr.Zero);

        string repoRoot = FindRepoRoot();
        RuleSource = File.ReadAllText(Path.Combine(repoRoot, "rules", "velocity_limits.ruledsl.txt"));

        using var engine = new RuleDSLEngine();
        var bytecode = engine.Compile(RuleSource);

        DisposeIsIdempotent();
        AfterDisposeEveryCallThrows(bytecode);
        ConcurrentDisposeNeverYieldsEmptyOutputs();
        ConcurrentEvaluationsDoNotCrossContaminate(engine, bytecode);
        ReadersAreSafeAlongsideEvaluations(engine, bytecode);
        NulStringIsRefused(engine, bytecode);
        UnsafeIntegerIsRefused(engine, bytecode);
        LongMinValueIsRefusedNotOverflowed(engine, bytecode);
        NonFiniteIsRefused(engine, bytecode);
        MalformedFieldEntriesAreRefused(engine, bytecode);
        NowUtcMsIsAnExactInteger(engine, bytecode);
        ClockAsAFieldEnforcesTheSameRules(engine, bytecode);
        BothClockSourcesAreRefused(engine, bytecode);
        UnencodableTextIsRefused(engine, bytecode);
        CleanupSurvivesAFailedEvaluation(engine, bytecode);
        NulRuleSourceIsRefused(engine);
        ReentrancyGuardIsPresent();

        Console.WriteLine($"\n{_passed} passed, {_failed} failed");
        return _failed == 0 ? 0 : 1;
    }

    // -----------------------------------------------------------------------
    // Harness
    // -----------------------------------------------------------------------

    private static void Test(string name, Action body)
    {
        try
        {
            body();
            _passed++;
            Console.WriteLine($"  PASS  {name}");
        }
        catch (Exception e)
        {
            _failed++;
            Console.WriteLine($"  FAIL  {name}: {e.Message}");
        }
    }

    private static void AssertTrue(bool cond, string msg)
    {
        if (!cond) throw new Exception(msg);
    }

    private static void AssertEq(object? actual, object? expected, string msg = "")
    {
        if (!Equals(actual, expected))
            throw new Exception($"Expected {expected}, got {actual}" +
                                (msg.Length > 0 ? $" ({msg})" : ""));
    }

    /// <summary>Assert the action throws TException, optionally with a message fragment.</summary>
    private static TException AssertThrows<TException>(Action action, string contains = "")
        where TException : Exception
    {
        try
        {
            action();
        }
        catch (TException e)
        {
            if (contains.Length > 0 && !e.Message.Contains(contains))
                throw new Exception(
                    $"{typeof(TException).Name} message missing '{contains}': {e.Message}");
            return e;
        }
        catch (Exception e)
        {
            throw new Exception($"Expected {typeof(TException).Name}, got {e.GetType().Name}: {e.Message}");
        }
        throw new Exception($"{typeof(TException).Name} not thrown");
    }

    private static void AssertRuleDSLCode(Action action, AXErrorCode code, string contains = "")
    {
        var e = AssertThrows<RuleDSLException>(action, contains);
        AssertEq(e.Code, code, "error code");
    }

    private static string FindRepoRoot()
    {
        // RULEDSL_REPO_ROOT lets the suite run from a build output outside the
        // tree (comparing against an older binding, for instance).
        string configured = Environment.GetEnvironmentVariable("RULEDSL_REPO_ROOT") ?? "";
        if (configured.Length > 0) return configured;

        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir != null && !File.Exists(Path.Combine(dir.FullName, "MANIFEST.txt")))
            dir = dir.Parent;
        if (dir == null)
            throw new Exception(
                "could not locate the repository root; set RULEDSL_REPO_ROOT");
        return dir.FullName;
    }

    private static Dictionary<string, object> Fields(params (string, object)[] pairs)
    {
        var d = new Dictionary<string, object>();
        foreach (var (k, v) in pairs) d[k] = v;
        return d;
    }

    // -----------------------------------------------------------------------
    // Lifetime
    // -----------------------------------------------------------------------

    private static void DisposeIsIdempotent() => Test("dispose: idempotent", () =>
    {
        var e = new RuleDSLEngine();
        e.Dispose();
        e.Dispose(); // must be a no-op, not a double free
    });

    private static void AfterDisposeEveryCallThrows(Bytecode bytecode) =>
        Test("after dispose: every public call throws ObjectDisposedException", () =>
        {
            var e = new RuleDSLEngine();
            e.Dispose();
            // Version() and CheckCompatibility() previously took no lock and
            // performed no liveness check at all.
            AssertThrows<ObjectDisposedException>(() => e.Version());
            AssertThrows<ObjectDisposedException>(() => e.CheckCompatibility(bytecode));
            AssertThrows<ObjectDisposedException>(() => e.Compile(RuleSource));
            AssertThrows<ObjectDisposedException>(
                () => e.Evaluate(bytecode, Fields(("amount", 1.0)), NowUtcMs));
        });

    private static void ConcurrentDisposeNeverYieldsEmptyOutputs() =>
        Test("race: concurrent Dispose() never yields a 'successful' empty-output decision", () =>
        {
            // The regression this file exists for. Dispose(bool) did not take
            // _nativeLock and ThrowIfDisposed() ran outside it, so a Dispose
            // landing in that window freed the compiler under an in-flight
            // ax_eval_bytecode. A genuine use-after-free may abort the process;
            // a non-zero exit is the intended CI signal for that.
            for (int round = 0; round < 50; round++)
            {
                var e = new RuleDSLEngine();
                var bc = e.Compile(RuleSource);
                var barrier = new Barrier(2);
                var outcomes = new List<object>();
                var gate = new object();

                var worker = new Thread(() =>
                {
                    barrier.SignalAndWait();
                    for (int i = 0; i < 20; i++)
                    {
                        try
                        {
                            var d = e.Evaluate(bc, Fields(("amount", 30000.0)), NowUtcMs);
                            lock (gate) outcomes.Add(d);
                        }
                        catch (Exception ex)
                        {
                            lock (gate) outcomes.Add(ex);
                            return;
                        }
                    }
                });
                worker.Start();
                barrier.SignalAndWait();
                e.Dispose();
                AssertTrue(worker.Join(TimeSpan.FromSeconds(30)),
                    "worker did not finish: Dispose() deadlocked");

                lock (gate)
                {
                    foreach (var outcome in outcomes)
                    {
                        if (outcome is ObjectDisposedException) continue;
                        AssertTrue(outcome is Decision, $"unexpected outcome {outcome}");
                        var d = (Decision)outcome;
                        AssertEq(d.RuleName, "block_extreme");
                        AssertEq(d.Outputs.Count, ExtremeOutputs.Count,
                            "successful decision with silently dropped output fields " +
                            "- the use-after-free signature");
                        foreach (var kv in ExtremeOutputs)
                            AssertEq(d.Outputs[kv.Key], kv.Value);
                    }
                }
            }
        });

    private static void ConcurrentEvaluationsDoNotCrossContaminate(
        RuleDSLEngine engine, Bytecode bytecode) =>
        Test("race: concurrent evaluations do not cross-contaminate output fields", () =>
        {
            // ax_eval_output_field_count/at read compiler-GLOBAL state that the
            // next ax_eval_bytecode overwrites, so the read has to be in the
            // same critical section as the evaluation.
            // medium_hourly_cap: 1000 < amount <= 5000, risk_score = (amount / 1000) * 10
            var amounts = new List<double>();
            for (int i = 0; i < 8; i++) amounts.Add(1100.0 + 100.0 * i);

            var errors = new List<string>();
            var gate = new object();
            var start = new Barrier(amounts.Count);
            var threads = new List<Thread>();

            foreach (var amount in amounts)
            {
                double a = amount;
                var t = new Thread(() =>
                {
                    try
                    {
                        start.SignalAndWait();
                        for (int i = 0; i < 25; i++)
                        {
                            var d = engine.Evaluate(bytecode, Fields(("amount", a)), NowUtcMs);
                            if (!Equals(d.Outputs["risk_score"], (a / 1000.0) * 10))
                                lock (gate) { errors.Add($"{a} -> {d.Outputs["risk_score"]}"); return; }
                        }
                    }
                    catch (Exception ex)
                    {
                        lock (gate) errors.Add($"{a} -> {ex.GetType().Name}: {ex.Message}");
                    }
                });
                threads.Add(t);
                t.Start();
            }
            foreach (var t in threads)
                AssertTrue(t.Join(TimeSpan.FromSeconds(60)), "worker timed out");
            AssertEq(string.Join("; ", errors), "",
                "output fields crossed between concurrent evaluations");
        });

    private static void ReadersAreSafeAlongsideEvaluations(
        RuleDSLEngine engine, Bytecode bytecode) =>
        Test("race: Version()/CheckCompatibility() are safe alongside evaluations", () =>
        {
            var errors = new List<string>();
            var gate = new object();
            var stop = new ManualResetEventSlim(false);
            var readers = new List<Thread>();

            for (int i = 0; i < 4; i++)
            {
                var t = new Thread(() =>
                {
                    try
                    {
                        while (!stop.IsSet)
                        {
                            if (string.IsNullOrEmpty(engine.Version()))
                                lock (gate) { errors.Add("empty version"); return; }
                            if (!engine.CheckCompatibility(bytecode).Compatible)
                                lock (gate) { errors.Add("incompatible bytecode"); return; }
                        }
                    }
                    catch (Exception ex)
                    {
                        lock (gate) errors.Add($"{ex.GetType().Name}: {ex.Message}");
                    }
                });
                readers.Add(t);
                t.Start();
            }
            try
            {
                for (int i = 0; i < 100; i++)
                    engine.Evaluate(bytecode, Fields(("amount", 30000.0)), NowUtcMs);
            }
            finally
            {
                stop.Set();
                foreach (var t in readers) t.Join(TimeSpan.FromSeconds(30));
            }
            AssertEq(string.Join("; ", errors), "");
        });

    private static void ReentrancyGuardIsPresent() =>
        Test("reentrancy: the in-flight guard exists (no reachable callback path in C# yet)", () =>
        {
            // The Python binding exposes on_trace, so a callback can re-enter
            // the engine and call close() from inside a running native call.
            // C# declares trace_cb in NativeAXEvalOptions but never wires it,
            // so today there is NO reachable same-thread reentrancy path here
            // and the guard cannot be exercised end-to-end. It is kept in
            // lockstep with the Python side so that adding a callback surface
            // later cannot reintroduce the defect; this test pins its presence
            // so a "cleanup" cannot quietly drop it.
            var field = typeof(RuleDSLEngine).GetField(
                "_inNative", BindingFlags.NonPublic | BindingFlags.Instance);
            AssertTrue(field != null, "_inNative guard was removed from RuleDSLEngine");

            var destroy = typeof(RuleDSLEngine).GetMethod(
                "DestroyLocked", BindingFlags.NonPublic | BindingFlags.Instance);
            AssertTrue(destroy != null, "DestroyLocked was removed from RuleDSLEngine");
        });

    // -----------------------------------------------------------------------
    // Value fidelity
    // -----------------------------------------------------------------------

    private static void NulStringIsRefused(RuleDSLEngine engine, Bytecode bytecode) =>
        Test("fidelity: a string containing NUL is refused, not silently truncated", () =>
        {
            // An audit passed {"country": "TR\0KP"}: the record kept the whole
            // string while the engine matched a rule on "TR".
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 100.0), ("country", "TR\0KP")), NowUtcMs),
                AXErrorCode.InvalidArgument, "NUL");
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode, Fields(("a\0b", 1.0)), NowUtcMs),
                AXErrorCode.InvalidArgument, "NUL");
        });

    private static void UnsafeIntegerIsRefused(RuleDSLEngine engine, Bytecode bytecode) =>
        Test("fidelity: an integer beyond 2^53-1 is refused, not silently rounded", () =>
        {
            // 9007199254740993 was logged verbatim while the engine evaluated
            // 9007199254740992.
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 100.0), ("account", 9007199254740993L)), NowUtcMs),
                AXErrorCode.InvalidArgument);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 100.0), ("account", -9007199254740993L)), NowUtcMs),
                AXErrorCode.InvalidArgument);
            // The boundary itself is exactly representable and must be accepted.
            engine.Evaluate(bytecode,
                Fields(("amount", 100.0), ("account", RuleDSLEngine.MaxSafeInteger)), NowUtcMs);
            engine.Evaluate(bytecode,
                Fields(("amount", 100.0), ("account", -RuleDSLEngine.MaxSafeInteger)), NowUtcMs);
        });

    private static void LongMinValueIsRefusedNotOverflowed(
        RuleDSLEngine engine, Bytecode bytecode) =>
        Test("fidelity: long.MinValue is a clean rejection, not an OverflowException", () =>
        {
            // The bounds check must compare directly, never via Math.Abs:
            // Math.Abs(long.MinValue) throws OverflowException, which would turn
            // a clean rejection into an unrelated crash on exactly the input
            // most likely to be hostile.
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 100.0), ("account", long.MinValue)), NowUtcMs),
                AXErrorCode.InvalidArgument);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 100.0), ("account", long.MaxValue)), NowUtcMs),
                AXErrorCode.InvalidArgument);
        });

    private static void NonFiniteIsRefused(RuleDSLEngine engine, Bytecode bytecode) =>
        Test("fidelity: non-finite floats report NonFinite", () =>
        {
            foreach (double v in new[] { double.NaN, double.PositiveInfinity, double.NegativeInfinity })
                AssertRuleDSLCode(
                    () => engine.Evaluate(bytecode, Fields(("amount", v)), NowUtcMs),
                    AXErrorCode.NonFinite);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode, Fields(("amount", float.NaN)), NowUtcMs),
                AXErrorCode.NonFinite);
        });

    private static void MalformedFieldEntriesAreRefused(
        RuleDSLEngine engine, Bytecode bytecode) =>
        Test("fidelity: unsupported and malformed field entries are refused", () =>
        {
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 1.0), ("x", new int[] { 1, 2 })), NowUtcMs),
                AXErrorCode.InvalidArgument);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 1.0), ("x", new Dictionary<string, object>())), NowUtcMs),
                AXErrorCode.InvalidArgument);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode, Fields(("", 1.0)), NowUtcMs),
                AXErrorCode.InvalidArgument);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode, null!, NowUtcMs),
                AXErrorCode.InvalidArgument);
            AssertRuleDSLCode(
                () => engine.Evaluate(null!, Fields(("amount", 1.0)), NowUtcMs),
                AXErrorCode.InvalidArgument);
        });

    private static void NowUtcMsIsAnExactInteger(RuleDSLEngine engine, Bytecode bytecode) =>
        Test("clock: nowUtcMs is an exact integer, never coerced", () =>
        {
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode, Fields(("amount", 1.0)), double.NaN),
                AXErrorCode.NonFinite);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode, Fields(("amount", 1.0)), 1700000000000.5),
                AXErrorCode.InvalidArgument);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode, Fields(("amount", 1.0)), 9007199254740992.0),
                AXErrorCode.InvalidArgument);
            // The advertised MCP schema declares minimum 0; both bindings agree.
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode, Fields(("amount", 1.0)), -1.0),
                AXErrorCode.InvalidArgument);
            // The accepted spelling still works.
            var d = engine.Evaluate(bytecode, Fields(("amount", 30000.0)), NowUtcMs);
            AssertEq(d.RuleName, "block_extreme");
        });

    private static void ClockAsAFieldEnforcesTheSameRules(
            RuleDSLEngine engine, Bytecode bytecode) =>
        Test("clock: the now_utc_ms FIELD path enforces the identical corpus", () =>
        {
            // Evaluate()'s own docs say the clock may arrive "via this argument
            // or a now_utc_ms field", but only the argument was ever checked,
            // so a fractional, negative or non-numeric field clock went
            // straight into evaluation.
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 1.0), ("now_utc_ms", double.NaN))),
                AXErrorCode.NonFinite);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 1.0), ("now_utc_ms", 1700000000000.5))),
                AXErrorCode.InvalidArgument);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 1.0), ("now_utc_ms", 9007199254740992.0))),
                AXErrorCode.InvalidArgument);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 1.0), ("now_utc_ms", -1.0))),
                AXErrorCode.InvalidArgument);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 1.0), ("now_utc_ms", "1700000000000"))),
                AXErrorCode.NowUtcMsNotNumber);
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 1.0), ("now_utc_ms", true))),
                AXErrorCode.NowUtcMsNotNumber);
            // A valid field clock still works.
            var d = engine.Evaluate(bytecode,
                Fields(("amount", 30000.0), ("now_utc_ms", NowUtcMs)));
            AssertEq(d.RuleName, "block_extreme");
        });

    private static void BothClockSourcesAreRefused(RuleDSLEngine engine, Bytecode bytecode) =>
        Test("clock: supplying both an argument and a field is refused", () =>
        {
            // The argument used to overwrite the field with no diagnostic, so
            // the caller's field value silently did not apply.
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 1.0), ("now_utc_ms", 1.0)), NowUtcMs),
                AXErrorCode.InvalidArgument, "both");
        });

    private static void UnencodableTextIsRefused(RuleDSLEngine engine, Bytecode bytecode) =>
        Test("fidelity: text with no UTF-8 form is refused, never replaced", () =>
        {
            // A .NET string is UTF-16 and may hold an unpaired surrogate.
            // Encoding.UTF8 silently substitutes U+FFFD, so the engine would
            // evaluate a character the caller never sent - the same defect the
            // NUL and 2^53 guards exist to prevent. Python raises here too.
            string lone = "TR\ud800KP";
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 1.0), ("c", lone)), NowUtcMs),
                AXErrorCode.InvalidArgument, "UTF-8");
            AssertRuleDSLCode(
                () => engine.Evaluate(bytecode,
                    Fields(("amount", 1.0), (lone, "x")), NowUtcMs),
                AXErrorCode.InvalidArgument, "UTF-8");
            AssertRuleDSLCode(
                () => engine.Compile("rule a { when amount > 1; then allow; }// " + lone),
                AXErrorCode.InvalidArgument, "UTF-8");
            // The engine is untouched by the refusals.
            var d = engine.Evaluate(bytecode, Fields(("amount", 30000.0)), NowUtcMs);
            AssertEq(d.RuleName, "block_extreme");
        });

    private static void CleanupSurvivesAFailedEvaluation(
            RuleDSLEngine engine, Bytecode bytecode) =>
        Test("cleanup: a refused evaluation leaves the engine reusable", () =>
        {
            // ax_decision_reset and ax_bytecode_free moved into finally blocks.
            // There is no reachable way to fail between the native call and the
            // reset from managed code today, so this pins the observable
            // consequence: a run of refusals interleaved with real evaluations
            // never disturbs a later decision.
            for (int i = 0; i < 20; i++)
            {
                AssertRuleDSLCode(
                    () => engine.Evaluate(bytecode,
                        Fields(("amount", 1.0), ("c", "TR\0KP")), NowUtcMs),
                    AXErrorCode.InvalidArgument);
                var d = engine.Evaluate(bytecode, Fields(("amount", 30000.0)), NowUtcMs);
                AssertEq(d.RuleName, "block_extreme");
                AssertEq(d.Outputs.Count, ExtremeOutputs.Count, "outputs after a refusal");
            }
        });

    private static void NulRuleSourceIsRefused(RuleDSLEngine engine) =>
        Test("compile: a rule source containing NUL is refused", () =>
        {
            // A NUL ends the C string: the compiler would silently compile only
            // the prefix while a hash over the file attests to all of its bytes.
            AssertRuleDSLCode(
                () => engine.Compile("rule a { when amount > 1; then allow; }\0" +
                                     "rule b { when amount > 2; then decline; }"),
                AXErrorCode.InvalidArgument, "NUL");
            AssertRuleDSLCode(() => engine.Compile(null!), AXErrorCode.InvalidArgument);
        });
}
