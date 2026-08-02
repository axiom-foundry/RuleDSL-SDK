// RuleDSL C# Binding — P/Invoke wrapper for the RuleDSL C API.
//
// Usage:
//   using Axiom.RuleDSL;
//
//   using var engine = new RuleDSLEngine();
//   var bytecode = engine.Compile("rule r1 { when amount > 100; then decline; }");
//   var decision = engine.Evaluate(bytecode, new Dictionary<string, object> {
//       { "amount", 1200.0 },
//       { "currency", "USD" },
//   });
//   Console.WriteLine(decision.Action); // "DECLINE"
//
// Requires: .NET 6+. Marshal.PtrToStringUTF8 and nullable reference types are
// used throughout, neither of which exists on .NET Framework; CI builds and
// tests net6.0 and net8.0, and the claim is limited to what is actually built.

using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace Axiom.RuleDSL
{
    // -----------------------------------------------------------------------
    // Error codes (frozen, append-only)
    // -----------------------------------------------------------------------

    public enum AXErrorCode
    {
        OK = 0,
        InvalidArgument = 1,
        Compile = 2,
        Verify = 3,
        MissingNowUtcMs = 4,
        NowUtcMsNotNumber = 5,
        NonFinite = 6,
        DivZero = 7,
        ConcurrentCompilerUse = 8,
        LimitExceeded = 9,
        BadStructSize = 10,
        Runtime = 11,
    }

    public enum AXActionType
    {
        Allow = 0,
        Decline = 1,
        Review = 2,
        Limit = 3,
    }

    public enum AXValueType
    {
        Missing = 0,
        Number = 1,
        String = 2,
        Ident = 3,
        Bool = 4,
    }

    public enum AXStatus
    {
        OK = 0,
        InvalidArgument = 1,
        BadStructSize = 2,
        StructurallyInvalid = 6,
        UnsupportedVersion = 7,
        CorruptedPayload = 8,
    }

    // -----------------------------------------------------------------------
    // Exceptions
    // -----------------------------------------------------------------------

    public class RuleDSLException : Exception
    {
        public AXErrorCode Code { get; }
        public string Detail { get; }

        public RuleDSLException(AXErrorCode code, string message, string detail = "")
            : base($"{code} (code={(int)code}): {message}" +
                   (string.IsNullOrEmpty(detail) ? "" : $" | detail: {detail}"))
        {
            Code = code;
            Detail = detail ?? "";
        }
    }

    public class CompileException : RuleDSLException
    {
        public CompileException(string message, string detail = "")
            : base(AXErrorCode.Compile, message, detail) { }
    }

    public class VerifyException : RuleDSLException
    {
        public VerifyException(string message, string detail = "")
            : base(AXErrorCode.Verify, message, detail) { }
    }

    public class EvalException : RuleDSLException
    {
        public EvalException(AXErrorCode code, string message, string detail = "")
            : base(code, message, detail) { }
    }

    // -----------------------------------------------------------------------
    // Currency-tagged numeric value
    // -----------------------------------------------------------------------

    /// <summary>
    /// A numeric value with an attached currency tag (e.g., 100.0 USD).
    /// Pass as a field value to attach currency metadata.
    /// </summary>
    public class CurrencyValue
    {
        public double Amount { get; }
        public string Currency { get; }

        public CurrencyValue(double amount, string currency)
        {
            Amount = amount;
            Currency = currency ?? throw new ArgumentNullException(nameof(currency));
        }
    }

    // -----------------------------------------------------------------------
    // Decision result
    // -----------------------------------------------------------------------

    public class Decision
    {
        public bool Matched { get; }
        public AXActionType ActionType { get; }
        public string Action { get; }
        public double Amount { get; }
        public string? Currency { get; }
        public double WindowCount { get; }
        public string? WindowUnit { get; }
        public string? RuleName { get; }
        public IReadOnlyDictionary<string, object?> Outputs { get; }

        private static readonly string[] ActionNames = { "ALLOW", "DECLINE", "REVIEW", "LIMIT" };

        internal Decision(bool matched, AXActionType actionType, double amount,
                          string? currency, double windowCount, string? windowUnit,
                          string? ruleName,
                          Dictionary<string, object?>? outputs = null)
        {
            Matched = matched;
            ActionType = actionType;
            Action = (int)actionType < ActionNames.Length
                ? ActionNames[(int)actionType]
                : $"UNKNOWN({(int)actionType})";
            Amount = amount;
            Currency = currency;
            WindowCount = windowCount;
            WindowUnit = windowUnit;
            RuleName = ruleName;
            Outputs = outputs ?? new Dictionary<string, object?>();
        }

        public override string ToString()
        {
            if (!Matched) return "Decision(matched=false)";
            var sb = new StringBuilder($"Decision(matched=true, action={Action}");
            if (!string.IsNullOrEmpty(RuleName)) sb.Append($", rule={RuleName}");
            if (ActionType == AXActionType.Limit)
            {
                sb.Append($", amount={Amount}");
                if (!string.IsNullOrEmpty(Currency)) sb.Append($", currency={Currency}");
                if (!string.IsNullOrEmpty(WindowUnit)) sb.Append($", window={WindowCount} {WindowUnit}");
            }
            if (Outputs.Count > 0)
            {
                sb.Append(", outputs={");
                bool first = true;
                foreach (var kv in Outputs)
                {
                    if (!first) sb.Append(", ");
                    sb.Append($"{kv.Key}={kv.Value}");
                    first = false;
                }
                sb.Append('}');
            }
            sb.Append(')');
            return sb.ToString();
        }
    }

    // -----------------------------------------------------------------------
    // Bytecode wrapper
    // -----------------------------------------------------------------------

    public class Bytecode
    {
        public byte[] Data { get; }

        public Bytecode(byte[] data)
        {
            Data = data ?? throw new ArgumentNullException(nameof(data));
        }

        public static Bytecode FromFile(string path)
        {
            return new Bytecode(System.IO.File.ReadAllBytes(path));
        }

        public void Save(string path)
        {
            System.IO.File.WriteAllBytes(path, Data);
        }

        public int Length => Data.Length;
    }

    // -----------------------------------------------------------------------
    // Native interop structs
    // -----------------------------------------------------------------------

    [StructLayout(LayoutKind.Sequential)]
    internal struct NativeAXValue
    {
        public int type;
        public double number;
        public IntPtr text;
        public int boolean_;
        public IntPtr currency;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct NativeAXField
    {
        public IntPtr name;
        public NativeAXValue value;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct NativeAXBytecode
    {
        public IntPtr data;
        public UIntPtr size;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct NativeAXEvalOptions
    {
        public uint struct_size;
        public IntPtr trace_cb;
        public IntPtr trace_user;
        public ulong reserved0, reserved1, reserved2, reserved3;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct NativeAXDecision
    {
        public uint struct_size;
        public int matched;
        public int action_type;
        public double amount;
        public IntPtr currency;
        public double window_count;
        public IntPtr window_unit;
        public IntPtr rule_name;
        public ulong reserved0, reserved1, reserved2, reserved3;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct NativeAXCompatibilityInfo
    {
        public uint struct_size;
        public uint axbc_version;
        public ushort lang_major;
        public ushort lang_minor;
        public ushort minimum_engine_abi;
        public ushort flags;
        public int compatibility_status;
        public ulong reserved0, reserved1, reserved2, reserved3;
    }

    // -----------------------------------------------------------------------
    // Native function imports
    // -----------------------------------------------------------------------

    internal static class NativeMethods
    {
        // Library name — resolved at runtime via NativeLibrary or DllImport
        private const string LibName = "ruledsl_capi";

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern IntPtr ax_compiler_create();

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern void ax_compiler_destroy(IntPtr compiler);

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ax_compiler_build(IntPtr compiler, byte[] err, UIntPtr err_len);

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ax_compile_to_bytecode(
            IntPtr compiler, byte[] input, ref NativeAXBytecode output,
            byte[] err, UIntPtr err_len);

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ax_eval_bytecode(
            IntPtr compiler, ref NativeAXBytecode bytecode,
            [In] NativeAXField[] fields, uint field_count,
            ref NativeAXEvalOptions options, ref NativeAXDecision decision,
            byte[] err, UIntPtr err_len);

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ax_check_bytecode_compatibility(
            byte[] bytecode, UIntPtr size, ref NativeAXCompatibilityInfo info);

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern void ax_bytecode_free(ref NativeAXBytecode bytecode);

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern void ax_decision_reset(ref NativeAXDecision decision);

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern void ax_free(IntPtr ptr);

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern IntPtr ax_version_string();

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern IntPtr ax_error_to_string(int code);

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ax_last_error_code();

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern UIntPtr ax_last_error_detail_utf8(byte[] buf, UIntPtr cap);

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern void ax_clear_last_error();

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern uint ax_eval_output_field_count(IntPtr compiler);

        [DllImport(LibName, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ax_eval_output_field_at(
            IntPtr compiler, uint index, out IntPtr out_name, out NativeAXValue out_value);
    }

    // -----------------------------------------------------------------------
    // Main API class
    // -----------------------------------------------------------------------

    /// <summary>
    /// RuleDSL engine wrapper. Thread-safe: an internal lock serializes ALL
    /// native calls — including Version() and CheckCompatibility() — so a
    /// single instance can be shared across threads.
    ///
    /// Lifetime: Dispose() waits for any in-flight call on this instance to
    /// return before destroying the compiler. Destroying it under a running
    /// call is a use-after-free that the engine cannot detect: it surfaces as
    /// a "successful" decision with silently empty output fields, or a crash.
    /// The finalizer never blocks — if a call is in flight it skips
    /// destruction, because a leaked compiler is reclaimed at process exit and
    /// a use-after-free is not.
    ///
    /// Implements IDisposable for deterministic cleanup.
    /// </summary>
    public class RuleDSLEngine : IDisposable
    {
        /// <summary>
        /// Largest integer that survives a round trip through IEEE 754
        /// binary64, the only numeric type the engine has. An integer beyond
        /// this converts to a DIFFERENT number, so the binding would evaluate
        /// something other than what the caller passed.
        /// </summary>
        public const long MaxSafeInteger = 9007199254740991L; // 2^53 - 1

        // Locking discipline: every member that reads _compiler/_disposed or
        // calls through NativeMethods holds _nativeLock, and ThrowIfDisposed()
        // is called with it already held.
        //
        // lock is Monitor, i.e. REENTRANT: a callback path that re-enters the
        // engine would be able to Dispose() from inside a running native call.
        // _inNative counts the native calls this instance is currently inside,
        // and destruction is refused while it is non-zero.
        private IntPtr _compiler;
        private bool _disposed;
        private int _inNative;
        private readonly object _nativeLock = new object();

        /// <summary>
        /// Create and initialize a RuleDSL engine instance.
        /// The library must be discoverable via the system PATH or specified via
        /// NativeLibrary.SetDllImportResolver.
        /// </summary>
        public RuleDSLEngine()
        {
            _compiler = NativeMethods.ax_compiler_create();
            if (_compiler == IntPtr.Zero)
                throw new RuleDSLException(AXErrorCode.Runtime, "Failed to create compiler");

            var err = new byte[1024];
            int ok = NativeMethods.ax_compiler_build(_compiler, err, (UIntPtr)err.Length);
            if (ok == 0)
            {
                string msg = Encoding.UTF8.GetString(err).TrimEnd('\0');
                NativeMethods.ax_compiler_destroy(_compiler);
                _compiler = IntPtr.Zero;
                throw new RuleDSLException(AXErrorCode.Compile, $"Compiler build failed: {msg}");
            }
        }

        /// <summary>Compile rule source text to bytecode.</summary>
        /// <exception cref="RuleDSLException">
        /// ruleSource is null or contains a NUL character.
        /// </exception>
        public Bytecode Compile(string ruleSource)
        {
            if (ruleSource == null)
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    "ruleSource must not be null");
            // A NUL ends the C string: the compiler would silently compile only
            // the prefix while any hash over the source attests to all of it.
            int nul = ruleSource.IndexOf('\0');
            if (nul >= 0)
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    $"ruleSource contains a NUL character at offset {nul}; the compiler " +
                    "receives a NUL-terminated C string and would compile only the prefix");

            var input = EncodeForEngine("ruleSource", ruleSource);
            var bc = new NativeAXBytecode();
            var err = new byte[2048];

            lock (_nativeLock)
            {
                ThrowIfDisposed();
                _inNative++;
                try
                {
                    int ok = NativeMethods.ax_compile_to_bytecode(
                        _compiler, input, ref bc, err, (UIntPtr)err.Length);

                    // The free covers EVERY exit after the call, the
                    // compile-error return included: a partial-failure path
                    // that still allocated would otherwise leak for the
                    // lifetime of the process. Guarded on bc.data so an
                    // untouched struct is never handed back to the allocator.
                    try
                    {
                        if (ok == 0)
                        {
                            string msg = Encoding.UTF8.GetString(err).TrimEnd('\0');
                            string detail = GetLastErrorDetail();
                            NativeMethods.ax_clear_last_error();
                            throw new CompileException(msg, detail);
                        }

                        var data = new byte[(int)bc.size];
                        Marshal.Copy(bc.data, data, 0, data.Length);
                        return new Bytecode(data);
                    }
                    finally
                    {
                        if (bc.data != IntPtr.Zero)
                            NativeMethods.ax_bytecode_free(ref bc);
                    }
                }
                finally
                {
                    _inNative--;
                }
            }
        }

        /// <summary>
        /// Evaluate bytecode against input fields.
        /// </summary>
        /// <param name="bytecode">Compiled bytecode.</param>
        /// <param name="fields">Field name-value pairs. Values: double, string, bool, or null.</param>
        /// <param name="nowUtcMs">Epoch ms for time-based rules. Must be supplied explicitly
        /// (via this argument or a "now_utc_ms" field); the engine never reads the system clock —
        /// reproducibility requires an explicit value. Omitting it for a time-based rule throws
        /// EvalException (MISSING_NOW_UTC_MS).</param>
        public Decision Evaluate(Bytecode bytecode, Dictionary<string, object> fields,
                                 double? nowUtcMs = null)
        {
            if (bytecode == null)
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    "bytecode must not be null");
            if (fields == null)
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    "fields must not be null");

            // now_utc_ms is NEVER auto-injected from the system clock. A deterministic engine must
            // be a pure function of explicit inputs; reading the wall clock here would make the same
            // bytecode+input non-reproducible. Time-based rules require an explicit now_utc_ms
            // (argument or field); otherwise the engine reports MISSING_NOW_UTC_MS and this throws.
            //
            // BOTH documented entry points go through CheckNowUtcMs. Only the
            // argument used to be checked, so a fractional or negative clock
            // supplied as a field went straight into evaluation; and supplying
            // both let the argument overwrite the field with no diagnostic.
            bool inFields = fields.ContainsKey("now_utc_ms");
            if (nowUtcMs.HasValue && inFields)
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    "now_utc_ms was supplied both as an argument and as a field; one " +
                    "would silently overwrite the other. Supply exactly one.");

            var allFields = new Dictionary<string, object>(fields);
            if (nowUtcMs.HasValue)
                allFields["now_utc_ms"] = CheckNowUtcMs(nowUtcMs.Value);
            else if (inFields)
                allFields["now_utc_ms"] = CheckNowUtcMs(ToClockDouble(fields["now_utc_ms"]));

            var handles = new List<GCHandle>();
            try
            {
                var nativeFields = BuildFields(allFields, handles);

                var nativeBc = new NativeAXBytecode();
                var bcHandle = GCHandle.Alloc(bytecode.Data, GCHandleType.Pinned);
                handles.Add(bcHandle);
                nativeBc.data = bcHandle.AddrOfPinnedObject();
                nativeBc.size = (UIntPtr)bytecode.Data.Length;

                var opts = new NativeAXEvalOptions
                {
                    struct_size = (uint)Marshal.SizeOf<NativeAXEvalOptions>()
                };

                var dec = new NativeAXDecision
                {
                    struct_size = (uint)Marshal.SizeOf<NativeAXDecision>()
                };

                var err = new byte[2048];

                Decision result;
                lock (_nativeLock)
                {
                    ThrowIfDisposed();
                    _inNative++;
                    try
                    {
                        int code = NativeMethods.ax_eval_bytecode(
                            _compiler, ref nativeBc, nativeFields, (uint)nativeFields.Length,
                            ref opts, ref dec, err, (UIntPtr)err.Length);

                        // From here on the engine owns the decision struct,
                        // so every exit resets it - the engine's own error
                        // return below included, which used to skip the reset
                        // entirely. See the finally at the end of this block.
                        if (code != 0)
                        {
                            string msg = Encoding.UTF8.GetString(err).TrimEnd('\0');
                            string detail = GetLastErrorDetail();
                            NativeMethods.ax_clear_last_error();
                            if ((AXErrorCode)code == AXErrorCode.Verify)
                                throw new VerifyException(msg, detail);
                            throw new EvalException((AXErrorCode)code, msg, detail);
                        }

                        // Collect output fields assigned in THEN clauses.
                        // The lock is load-bearing for CORRECTNESS here, not
                        // merely defensive: ax_eval_output_field_count/at read
                        // compiler-GLOBAL state that the next ax_eval_bytecode
                        // overwrites, so the read must happen in the same
                        // critical section as the evaluation.
                        var outputs = new Dictionary<string, object?>();
                        uint outputCount = NativeMethods.ax_eval_output_field_count(_compiler);
                        for (uint idx = 0; idx < outputCount; idx++)
                        {
                            int rc = NativeMethods.ax_eval_output_field_at(
                                _compiler, idx, out IntPtr namePtr, out NativeAXValue val);
                            if (rc == 0 && namePtr != IntPtr.Zero)
                            {
                                string name = DecodeResult("output field name", namePtr);
                                object? value = (AXValueType)val.type switch
                                {
                                    AXValueType.Number => val.number,
                                    AXValueType.String or AXValueType.Ident => val.text != IntPtr.Zero
                                        ? DecodeResult($"output field '{name}'", val.text) : "",
                                    AXValueType.Bool => val.boolean_ != 0,
                                    _ => null,
                                };
                                outputs[name] = value;
                            }
                        }

                        result = new Decision(
                            matched: dec.matched != 0,
                            actionType: (AXActionType)dec.action_type,
                            amount: dec.amount,
                            currency: dec.currency != IntPtr.Zero
                                ? DecodeResult("currency", dec.currency) : null,
                            windowCount: dec.window_count,
                            windowUnit: dec.window_unit != IntPtr.Zero
                                ? DecodeResult("window_unit", dec.window_unit) : null,
                            ruleName: dec.rule_name != IntPtr.Zero
                                ? DecodeResult("rule_name", dec.rule_name) : null,
                            outputs: outputs
                        );
                    }
                    finally
                    {
                        // In a finally: a decode failure above must still
                        // release the native decision, and the next evaluation
                        // must not inherit this one's state.
                        NativeMethods.ax_decision_reset(ref dec);
                        _inNative--;
                    }
                }
                return result;
            }
            finally
            {
                foreach (var h in handles)
                    if (h.IsAllocated) h.Free();
            }
        }

        /// <summary>Check bytecode compatibility with the current engine.</summary>
        public (bool Compatible, AXStatus Status, uint AxbcVersion,
                ushort LangMajor, ushort LangMinor, ushort MinimumEngineAbi) CheckCompatibility(Bytecode bytecode)
        {
            var info = new NativeAXCompatibilityInfo
            {
                struct_size = (uint)Marshal.SizeOf<NativeAXCompatibilityInfo>()
            };

            // ax_check_bytecode_compatibility takes no compiler handle, but it
            // is still a native call on a disposable instance: locking makes
            // "called after Dispose()" a stable ObjectDisposedException.
            int status;
            lock (_nativeLock)
            {
                ThrowIfDisposed();
                status = NativeMethods.ax_check_bytecode_compatibility(
                    bytecode.Data, (UIntPtr)bytecode.Data.Length, ref info);
            }

            return (status == 0, (AXStatus)status, info.axbc_version,
                    info.lang_major, info.lang_minor, info.minimum_engine_abi);
        }

        /// <summary>Get the engine version string.</summary>
        public string Version()
        {
            IntPtr ptr;
            lock (_nativeLock)
            {
                ThrowIfDisposed();
                ptr = NativeMethods.ax_version_string();
            }
            return ptr != IntPtr.Zero ? Marshal.PtrToStringUTF8(ptr) ?? "unknown" : "unknown";
        }

        // -- IDisposable ------------------------------------------------------

        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }

        /// <param name="disposing">
        /// True from Dispose(): it is safe to block until in-flight calls
        /// return. False from the finalizer: never block there.
        /// </param>
        protected virtual void Dispose(bool disposing)
        {
            if (disposing)
            {
                lock (_nativeLock)
                {
                    DestroyLocked(throwIfInNative: true);
                }
                return;
            }

            // Finalizer thread: take the lock only if it is free, and skip
            // destruction entirely if a call is in flight. Leaking a compiler
            // that the process is about to drop is strictly better than
            // freeing it under a running native call.
            if (Monitor.TryEnter(_nativeLock))
            {
                try
                {
                    DestroyLocked(throwIfInNative: false);
                }
                catch
                {
                    // A finalizer must never throw.
                }
                finally
                {
                    Monitor.Exit(_nativeLock);
                }
            }
        }

        ~RuleDSLEngine() => Dispose(false);

        // -- Internal ---------------------------------------------------------

        /// <summary>Destroy the compiler. Caller MUST hold _nativeLock.</summary>
        private void DestroyLocked(bool throwIfInNative)
        {
            if (_inNative > 0)
            {
                // Reentrant destruction: this thread is inside a native call on
                // this very instance (lock is Monitor, so it re-entered), and
                // destroying the compiler here would free it under that call.
                if (throwIfInNative)
                    throw new InvalidOperationException(
                        "Dispose() called from inside an in-flight engine call; " +
                        "destroying the compiler here would be a use-after-free. " +
                        "Dispose after the call returns.");
                return;
            }

            if (!_disposed && _compiler != IntPtr.Zero)
            {
                // Clear the field before destroying so no second path can free it.
                IntPtr compiler = _compiler;
                _compiler = IntPtr.Zero;
                NativeMethods.ax_compiler_destroy(compiler);
            }
            _disposed = true;
        }

        /// <summary>Callers MUST hold _nativeLock.</summary>
        private void ThrowIfDisposed()
        {
            if (_disposed)
                throw new ObjectDisposedException(nameof(RuleDSLEngine));
        }

        /// <summary>
        /// Validate the explicit clock. now_utc_ms is epoch MILLISECONDS: an
        /// integer. A fractional or out-of-range value would be evaluated as a
        /// different instant than the caller intended.
        /// </summary>
        private static double CheckNowUtcMs(double value)
        {
            if (double.IsNaN(value) || double.IsInfinity(value))
                throw new EvalException(AXErrorCode.NonFinite,
                    $"now_utc_ms must be finite, got {value}", "");
            if (value != Math.Floor(value))
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    $"now_utc_ms is epoch milliseconds and must be a whole number, got {value}");
            // Direct bounds, never Math.Abs: Math.Abs(long.MinValue) throws.
            if (value > MaxSafeInteger)
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    $"now_utc_ms {value} is outside the exactly representable range " +
                    "(value > 2^53-1)");
            // Epoch milliseconds are counted from 1970; a negative value is a
            // unit or sign mistake far more often than a deliberate pre-1970
            // timestamp, and the MCP layer advertises minimum 0. Same rule in
            // both bindings and at both layers.
            if (value < 0)
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    $"now_utc_ms {value} is negative; epoch milliseconds start at " +
                    "0 (1970-01-01T00:00:00Z)");
            return value;
        }

        /// <summary>
        /// Read a clock supplied as a FIELD, refusing anything that is not a
        /// number. A boxed string or bool here would otherwise be marshalled
        /// as an ordinary field and the rule would simply fail to match,
        /// which reads as "no rule applied" rather than as an error.
        /// </summary>
        private static double ToClockDouble(object? value)
        {
            switch (value)
            {
                case double d: return d;
                case float f: return f;
                case long l: return l;
                case int i: return i;
                default:
                    throw new EvalException(AXErrorCode.NowUtcMsNotNumber,
                        "now_utc_ms must be a number, got " +
                        (value?.GetType().Name ?? "null"), "");
            }
        }

        /// <summary>
        /// UTF-8 with no silent substitution, in either direction.
        /// </summary>
        /// <remarks>
        /// The default UTF8Encoding replaces anything it cannot represent with
        /// U+FFFD and says nothing. On the way in, a .NET string is UTF-16 and
        /// may hold an unpaired surrogate, so the engine would evaluate a
        /// replacement character while the caller believed otherwise; on the
        /// way out, a decision string would be silently corrupted before being
        /// recorded. Python raises in both directions, so a throwing encoder
        /// here is also what keeps the two bindings behaving alike.
        /// </remarks>
        private static readonly UTF8Encoding StrictUtf8 =
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false,
                             throwOnInvalidBytes: true);

        /// <summary>Encode text for the engine, refusing anything without a
        /// faithful UTF-8 form. Appends the NUL the C API expects.</summary>
        private static byte[] EncodeForEngine(string what, string text)
        {
            try
            {
                return StrictUtf8.GetBytes(text + '\0');
            }
            catch (EncoderFallbackException ex)
            {
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    $"{what} is not encodable as UTF-8 ({ex.Message}); the engine " +
                    "receives UTF-8 bytes and this string has no faithful representation");
            }
        }

        /// <summary>Decode engine-produced DECISION text strictly.</summary>
        /// <remarks>
        /// Marshal.PtrToStringUTF8 substitutes U+FFFD without complaint, which
        /// would put a character the engine never produced into a decision the
        /// caller then records. Diagnostics (error text, last-error detail) keep
        /// the lenient decoder: they are prose about a failure, not decision data.
        /// </remarks>
        private static string DecodeResult(string what, IntPtr ptr)
        {
            int length = 0;
            while (Marshal.ReadByte(ptr, length) != 0)
                length++;
            var bytes = new byte[length];
            Marshal.Copy(ptr, bytes, 0, length);
            try
            {
                return StrictUtf8.GetString(bytes);
            }
            catch (DecoderFallbackException ex)
            {
                throw new RuleDSLException(AXErrorCode.Runtime,
                    $"engine returned {what} as invalid UTF-8 ({ex.Message}); refusing " +
                    "to substitute replacement characters into a decision");
            }
        }

        /// <summary>
        /// Reject anything the engine cannot receive faithfully. The engine
        /// sees fields as AXValue: a double, a NUL-terminated C string, a bool,
        /// or missing. A value that survives that boundary only partially makes
        /// the binding report an input the engine never evaluated.
        /// </summary>
        private static void CheckField(string name, object? value)
        {
            if (string.IsNullOrEmpty(name))
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    "Field names must be non-empty strings");
            if (name.IndexOf('\0') >= 0)
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    $"Field name '{Brief(name)}' contains a NUL character; the engine receives a " +
                    "NUL-terminated C string and would see only the prefix");
            EncodeForEngine($"Field name '{Brief(name)}'", name);

            switch (value)
            {
                case null:
                case bool:
                    return;
                case double d:
                    CheckFinite(name, d);
                    return;
                case float f:
                    CheckFinite(name, f);
                    return;
                case int:
                    return; // every int is exactly representable as a double
                case long l:
                    CheckSafeInteger(name, l);
                    return;
                case CurrencyValue cv:
                    CheckFinite(name, cv.Amount);
                    if (cv.Currency != null && cv.Currency.IndexOf('\0') >= 0)
                        throw new RuleDSLException(AXErrorCode.InvalidArgument,
                            $"Field '{Brief(name)}': currency contains a NUL character");
                    if (cv.Currency != null)
                        EncodeForEngine($"Field '{Brief(name)}': currency", cv.Currency);
                    return;
                case string s:
                    if (s.IndexOf('\0') >= 0)
                        throw new RuleDSLException(AXErrorCode.InvalidArgument,
                            $"Field '{Brief(name)}': string contains a NUL character; the engine " +
                            "receives a NUL-terminated C string and would see only the prefix");
                    EncodeForEngine($"Field '{Brief(name)}': string value", s);
                    return;
                default:
                    throw new RuleDSLException(AXErrorCode.InvalidArgument,
                        $"Unsupported field value type for '{Brief(name)}': {value.GetType().Name}. " +
                        "Use double, long, int, string, bool, CurrencyValue, or null.");
            }
        }

        /// <summary>
        /// Render caller-supplied text for an exception message, bounded.
        /// A 1 MiB field name must not become a 1 MiB exception: an error is
        /// never inflated by the input that caused it.
        /// </summary>
        private static string Brief(string? text)
        {
            if (text == null) return "null";
            return text.Length <= 64 ? text : text.Substring(0, 64) + "...(truncated)";
        }

        private static void CheckFinite(string name, double d)
        {
            if (double.IsNaN(d) || double.IsInfinity(d))
                throw new EvalException(AXErrorCode.NonFinite,
                    $"Field '{Brief(name)}': {d} is not a finite number", "");
        }

        private static void CheckSafeInteger(string name, long l)
        {
            // Direct bounds comparison, NOT Math.Abs(l): Math.Abs(long.MinValue)
            // throws OverflowException, which would turn a clean rejection into
            // an unrelated crash on the one input most likely to be hostile.
            if (l > MaxSafeInteger || l < -MaxSafeInteger)
                throw new RuleDSLException(AXErrorCode.InvalidArgument,
                    $"Field '{Brief(name)}': integer {l} is not exactly representable as float64 " +
                    "(|value| > 2^53-1); the engine would evaluate a different number. " +
                    "Pass identifiers as strings.");
        }

        private static string GetLastErrorDetail()
        {
            var buf = new byte[1024];
            NativeMethods.ax_last_error_detail_utf8(buf, (UIntPtr)buf.Length);
            return Encoding.UTF8.GetString(buf).TrimEnd('\0');
        }

        private static NativeAXField[] BuildFields(
            Dictionary<string, object> fields, List<GCHandle> handles)
        {
            // Validate-then-build: every pair is checked before any handle is
            // pinned, so a rejection halfway through cannot leave a partially
            // built field array (and its pinned handles) behind.
            foreach (var kv in fields)
                CheckField(kv.Key, kv.Value);

            var result = new NativeAXField[fields.Count];
            int i = 0;
            foreach (var kv in fields)
            {
                var nameBytes = EncodeForEngine($"Field name '{Brief(kv.Key)}'", kv.Key);
                var nameHandle = GCHandle.Alloc(nameBytes, GCHandleType.Pinned);
                handles.Add(nameHandle);

                result[i].name = nameHandle.AddrOfPinnedObject();
                result[i].value = MakeValue(kv.Value, handles);
                i++;
            }
            return result;
        }

        private static NativeAXValue MakeValue(object val, List<GCHandle> handles,
                                                string? currency = null)
        {
            var v = new NativeAXValue();

            switch (val)
            {
                case null:
                    v.type = (int)AXValueType.Missing;
                    break;
                case bool b:
                    v.type = (int)AXValueType.Bool;
                    v.boolean_ = b ? 1 : 0;
                    break;
                case double d:
                    v.type = (int)AXValueType.Number;
                    v.number = d;
                    break;
                case float f:
                    v.type = (int)AXValueType.Number;
                    v.number = f;
                    break;
                case int n:
                    v.type = (int)AXValueType.Number;
                    v.number = n;
                    break;
                case long l:
                    v.type = (int)AXValueType.Number;
                    v.number = l;
                    break;
                case CurrencyValue cv:
                    v.type = (int)AXValueType.Number;
                    v.number = cv.Amount;
                    var cvBytes = EncodeForEngine("currency", cv.Currency);
                    var cvHandle = GCHandle.Alloc(cvBytes, GCHandleType.Pinned);
                    handles.Add(cvHandle);
                    v.currency = cvHandle.AddrOfPinnedObject();
                    break;
                case string s:
                    v.type = (int)AXValueType.String;
                    var textBytes = EncodeForEngine("string value", s);
                    var textHandle = GCHandle.Alloc(textBytes, GCHandleType.Pinned);
                    handles.Add(textHandle);
                    v.text = textHandle.AddrOfPinnedObject();
                    break;
                default:
                    throw new RuleDSLException(AXErrorCode.InvalidArgument,
                        $"Unsupported field value type: {val.GetType().Name}. " +
                        "Use double, string, bool, or null.");
            }

            if (currency != null)
            {
                var curBytes = EncodeForEngine("currency", currency);
                var curHandle = GCHandle.Alloc(curBytes, GCHandleType.Pinned);
                handles.Add(curHandle);
                v.currency = curHandle.AddrOfPinnedObject();
            }

            return v;
        }
    }
}
