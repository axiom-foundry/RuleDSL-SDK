// RuleDSL C# Binding — P/Invoke wrapper for the RuleDSL C API.
//
// Usage:
//   using Axiom.RuleDSL;
//
//   using var engine = new RuleDSLEngine("ruledsl_capi.dll");
//   var bytecode = engine.Compile("rule r1 { when amount > 100; then decline; }");
//   var decision = engine.Evaluate(bytecode, new Dictionary<string, object> {
//       { "amount", 1200.0 },
//       { "currency", "USD" },
//   });
//   Console.WriteLine(decision.Action); // "DECLINE"
//
// Requires: .NET 6+ or .NET Framework 4.7.2+

using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

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

    public class EvalException : RuleDSLException
    {
        public EvalException(AXErrorCode code, string message, string detail = "")
            : base(code, message, detail) { }
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
    /// RuleDSL engine wrapper. Thread-safe if each thread uses its own instance.
    /// Implements IDisposable for deterministic cleanup.
    /// </summary>
    public class RuleDSLEngine : IDisposable
    {
        private IntPtr _compiler;
        private bool _disposed;

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
        public Bytecode Compile(string ruleSource)
        {
            ThrowIfDisposed();
            var input = Encoding.UTF8.GetBytes(ruleSource + '\0');
            var bc = new NativeAXBytecode();
            var err = new byte[2048];

            int ok = NativeMethods.ax_compile_to_bytecode(
                _compiler, input, ref bc, err, (UIntPtr)err.Length);

            if (ok == 0)
            {
                string msg = Encoding.UTF8.GetString(err).TrimEnd('\0');
                string detail = GetLastErrorDetail();
                NativeMethods.ax_clear_last_error();
                throw new CompileException(msg, detail);
            }

            var data = new byte[(int)bc.size];
            Marshal.Copy(bc.data, data, 0, data.Length);
            NativeMethods.ax_bytecode_free(ref bc);

            return new Bytecode(data);
        }

        /// <summary>
        /// Evaluate bytecode against input fields.
        /// </summary>
        /// <param name="bytecode">Compiled bytecode.</param>
        /// <param name="fields">Field name-value pairs. Values: double, string, bool, or null.</param>
        /// <param name="nowUtcMs">Epoch ms for time-based rules. If null, uses current time.</param>
        public Decision Evaluate(Bytecode bytecode, Dictionary<string, object> fields,
                                 double? nowUtcMs = null)
        {
            ThrowIfDisposed();

            var allFields = new Dictionary<string, object>(fields);
            if (!nowUtcMs.HasValue && !allFields.ContainsKey("now_utc_ms"))
                nowUtcMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            if (nowUtcMs.HasValue)
                allFields["now_utc_ms"] = nowUtcMs.Value;

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

                int code = NativeMethods.ax_eval_bytecode(
                    _compiler, ref nativeBc, nativeFields, (uint)nativeFields.Length,
                    ref opts, ref dec, err, (UIntPtr)err.Length);

                if (code != 0)
                {
                    string msg = Encoding.UTF8.GetString(err).TrimEnd('\0');
                    string detail = GetLastErrorDetail();
                    NativeMethods.ax_clear_last_error();
                    throw new EvalException((AXErrorCode)code, msg, detail);
                }

                // Collect output fields assigned in THEN clauses
                var outputs = new Dictionary<string, object?>();
                uint outputCount = NativeMethods.ax_eval_output_field_count(_compiler);
                for (uint idx = 0; idx < outputCount; idx++)
                {
                    int rc = NativeMethods.ax_eval_output_field_at(
                        _compiler, idx, out IntPtr namePtr, out NativeAXValue val);
                    if (rc == 0 && namePtr != IntPtr.Zero)
                    {
                        string? name = Marshal.PtrToStringUTF8(namePtr);
                        if (name != null)
                        {
                            object? value = (AXValueType)val.type switch
                            {
                                AXValueType.Number => val.number,
                                AXValueType.String => val.text != IntPtr.Zero
                                    ? Marshal.PtrToStringUTF8(val.text) : "",
                                AXValueType.Bool => val.boolean_ != 0,
                                _ => null,
                            };
                            outputs[name] = value;
                        }
                    }
                }

                var result = new Decision(
                    matched: dec.matched != 0,
                    actionType: (AXActionType)dec.action_type,
                    amount: dec.amount,
                    currency: dec.currency != IntPtr.Zero
                        ? Marshal.PtrToStringUTF8(dec.currency) : null,
                    windowCount: dec.window_count,
                    windowUnit: dec.window_unit != IntPtr.Zero
                        ? Marshal.PtrToStringUTF8(dec.window_unit) : null,
                    ruleName: dec.rule_name != IntPtr.Zero
                        ? Marshal.PtrToStringUTF8(dec.rule_name) : null,
                    outputs: outputs
                );

                NativeMethods.ax_decision_reset(ref dec);
                return result;
            }
            finally
            {
                foreach (var h in handles)
                    if (h.IsAllocated) h.Free();
            }
        }

        /// <summary>Check bytecode compatibility with the current engine.</summary>
        public (bool Compatible, AXStatus Status, uint AxbcVersion) CheckCompatibility(Bytecode bytecode)
        {
            var info = new NativeAXCompatibilityInfo
            {
                struct_size = (uint)Marshal.SizeOf<NativeAXCompatibilityInfo>()
            };

            int status = NativeMethods.ax_check_bytecode_compatibility(
                bytecode.Data, (UIntPtr)bytecode.Data.Length, ref info);

            return (status == 0, (AXStatus)status, info.axbc_version);
        }

        /// <summary>Get the engine version string.</summary>
        public string Version()
        {
            var ptr = NativeMethods.ax_version_string();
            return ptr != IntPtr.Zero ? Marshal.PtrToStringUTF8(ptr) ?? "unknown" : "unknown";
        }

        // -- IDisposable ------------------------------------------------------

        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }

        protected virtual void Dispose(bool disposing)
        {
            if (!_disposed && _compiler != IntPtr.Zero)
            {
                NativeMethods.ax_compiler_destroy(_compiler);
                _compiler = IntPtr.Zero;
            }
            _disposed = true;
        }

        ~RuleDSLEngine() => Dispose(false);

        // -- Internal ---------------------------------------------------------

        private void ThrowIfDisposed()
        {
            if (_disposed)
                throw new ObjectDisposedException(nameof(RuleDSLEngine));
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
            var result = new NativeAXField[fields.Count];
            int i = 0;
            foreach (var kv in fields)
            {
                var nameBytes = Encoding.UTF8.GetBytes(kv.Key + '\0');
                var nameHandle = GCHandle.Alloc(nameBytes, GCHandleType.Pinned);
                handles.Add(nameHandle);

                result[i].name = nameHandle.AddrOfPinnedObject();
                result[i].value = MakeValue(kv.Value, handles);
                i++;
            }
            return result;
        }

        private static NativeAXValue MakeValue(object val, List<GCHandle> handles)
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
                case string s:
                    v.type = (int)AXValueType.String;
                    var textBytes = Encoding.UTF8.GetBytes(s + '\0');
                    var textHandle = GCHandle.Alloc(textBytes, GCHandleType.Pinned);
                    handles.Add(textHandle);
                    v.text = textHandle.AddrOfPinnedObject();
                    break;
                default:
                    throw new RuleDSLException(AXErrorCode.InvalidArgument,
                        $"Unsupported field value type: {val.GetType().Name}. " +
                        "Use double, string, bool, or null.");
            }

            return v;
        }
    }
}
