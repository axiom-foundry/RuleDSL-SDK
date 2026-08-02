"""
RuleDSL Python Binding — ctypes wrapper for the RuleDSL C API.

Usage:
    from ruledsl import RuleDSL

    engine = RuleDSL("path/to/ruledsl_capi.dll")  # or .so on Linux

    bytecode = engine.compile('rule r1 { when amount > 100; then decline; }')
    decision = engine.evaluate(bytecode, {
        "amount": 1200.0,
        "currency": "USD",
    })

    print(decision.action)    # "DECLINE"
    print(decision.matched)   # True

Requires: Python 3.7+, no third-party dependencies.
"""

import ctypes
import ctypes.util
import math
import os
import platform
import threading
from pathlib import Path

# Largest integer that survives a round trip through IEEE 754 binary64, the
# only numeric type the engine has (AXValue.number is a double). An integer
# beyond this converts to a DIFFERENT number, so the binding would evaluate
# something other than what the caller passed and what an audit log records.
MAX_SAFE_INTEGER = 2 ** 53 - 1


# ---------------------------------------------------------------------------
# Error codes (frozen, append-only)
# ---------------------------------------------------------------------------

class ErrorCode:
    OK = 0
    INVALID_ARGUMENT = 1
    COMPILE = 2
    VERIFY = 3
    MISSING_NOW_UTC_MS = 4
    NOW_UTC_MS_NOT_NUMBER = 5
    NON_FINITE = 6
    DIV_ZERO = 7
    CONCURRENT_COMPILER_USE = 8
    LIMIT_EXCEEDED = 9
    BAD_STRUCT_SIZE = 10
    RUNTIME = 11

    _NAMES = {
        0: "AX_ERR_OK",
        1: "AX_ERR_INVALID_ARGUMENT",
        2: "AX_ERR_COMPILE",
        3: "AX_ERR_VERIFY",
        4: "AX_ERR_MISSING_NOW_UTC_MS",
        5: "AX_ERR_NOW_UTC_MS_NOT_NUMBER",
        6: "AX_ERR_NON_FINITE",
        7: "AX_ERR_DIV_ZERO",
        8: "AX_ERR_CONCURRENT_COMPILER_USE",
        9: "AX_ERR_LIMIT_EXCEEDED",
        10: "AX_ERR_BAD_STRUCT_SIZE",
        11: "AX_ERR_RUNTIME",
    }

    @classmethod
    def name(cls, code):
        return cls._NAMES.get(code, f"UNKNOWN({code})")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RuleDSLError(Exception):
    """Base exception for all RuleDSL errors."""

    def __init__(self, code, message, detail=""):
        self.code = code
        self.code_name = ErrorCode.name(code)
        self.detail = detail
        super().__init__(f"{self.code_name} (code={code}): {message}"
                         + (f" | detail: {detail}" if detail else ""))


class CompileError(RuleDSLError):
    """Rule compilation failed."""
    pass


class VerifyError(RuleDSLError):
    """Bytecode verification failed."""
    pass


class EvalError(RuleDSLError):
    """Evaluation failed."""
    pass


class ArgumentError(RuleDSLError):
    """Invalid argument passed to the API."""
    pass


_ERROR_CLASS = {
    ErrorCode.INVALID_ARGUMENT: ArgumentError,
    ErrorCode.COMPILE: CompileError,
    ErrorCode.VERIFY: VerifyError,
    ErrorCode.MISSING_NOW_UTC_MS: EvalError,
    ErrorCode.NOW_UTC_MS_NOT_NUMBER: EvalError,
    ErrorCode.NON_FINITE: EvalError,
    ErrorCode.DIV_ZERO: EvalError,
    ErrorCode.CONCURRENT_COMPILER_USE: EvalError,
    ErrorCode.LIMIT_EXCEEDED: EvalError,
    ErrorCode.BAD_STRUCT_SIZE: EvalError,
    ErrorCode.RUNTIME: EvalError,
}


# ---------------------------------------------------------------------------
# C struct definitions (ctypes)
# ---------------------------------------------------------------------------

class _AXValue(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("number", ctypes.c_double),
        ("text", ctypes.c_char_p),
        ("boolean", ctypes.c_int),
        ("currency", ctypes.c_char_p),
    ]


class _AXField(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("value", _AXValue),
    ]


class _AXBytecode(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_ubyte)),
        ("size", ctypes.c_size_t),
    ]


# Matches AXTraceCallback in ruledsl_c.h: void (*)(void* user, const char* line).
_AXTraceCallback = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_char_p)


class _AXEvalOptions(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("trace_cb", _AXTraceCallback),
        ("trace_user", ctypes.c_void_p),
        ("reserved", ctypes.c_uint64 * 4),
    ]


class _AXDecision(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("matched", ctypes.c_int),
        ("action_type", ctypes.c_int),
        ("amount", ctypes.c_double),
        ("currency", ctypes.c_char_p),
        ("window_count", ctypes.c_double),
        ("window_unit", ctypes.c_char_p),
        ("rule_name", ctypes.c_char_p),
        ("reserved", ctypes.c_uint64 * 4),
    ]


class _AXCompatibilityInfo(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("axbc_version", ctypes.c_uint32),
        ("lang_major", ctypes.c_uint16),
        ("lang_minor", ctypes.c_uint16),
        ("minimum_engine_abi", ctypes.c_uint16),
        ("flags", ctypes.c_uint16),
        ("compatibility_status", ctypes.c_int),
        ("reserved", ctypes.c_uint64 * 4),
    ]


# ---------------------------------------------------------------------------
# Value type constants
# ---------------------------------------------------------------------------

_VALUE_MISSING = 0
_VALUE_NUMBER = 1
_VALUE_STRING = 2
_VALUE_IDENT = 3
_VALUE_BOOL = 4

# Action type names
_ACTION_NAMES = {0: "ALLOW", 1: "DECLINE", 2: "REVIEW", 3: "LIMIT"}


# ---------------------------------------------------------------------------
# Decision result (Pythonic wrapper)
# ---------------------------------------------------------------------------

class Decision:
    """Immutable result of a rule evaluation."""

    __slots__ = ("matched", "action", "action_type", "amount", "currency",
                 "window_count", "window_unit", "rule_name", "outputs")

    def __init__(self, matched, action_type, amount, currency,
                 window_count, window_unit, rule_name, outputs=None):
        self.matched = bool(matched)
        self.action_type = action_type
        self.action = _ACTION_NAMES.get(action_type, f"UNKNOWN({action_type})")
        self.amount = amount
        self.currency = currency
        self.window_count = window_count
        self.window_unit = window_unit
        self.rule_name = rule_name
        self.outputs = outputs if outputs is not None else {}

    def __repr__(self):
        if not self.matched:
            return "Decision(matched=False)"
        parts = [f"action={self.action!r}"]
        if self.rule_name:
            parts.append(f"rule={self.rule_name!r}")
        if self.action_type == 3:  # LIMIT
            parts.append(f"amount={self.amount}")
            if self.currency:
                parts.append(f"currency={self.currency!r}")
            if self.window_unit:
                parts.append(f"window={self.window_count} {self.window_unit}")
        if self.outputs:
            parts.append(f"outputs={self.outputs!r}")
        return f"Decision(matched=True, {', '.join(parts)})"


# ---------------------------------------------------------------------------
# Bytecode wrapper
# ---------------------------------------------------------------------------

class Bytecode:
    """Wrapper around compiled bytecode. Holds raw bytes."""

    __slots__ = ("_data", "_c_buf")

    def __init__(self, data: bytes):
        self._data = data
        self._c_buf = None

    def _ctypes_buffer(self):
        # Built once and reused: the bytes are immutable and the engine only
        # reads from it, so rebuilding it per evaluate() call would be pure
        # overhead (it used to dominate the call cost).
        if self._c_buf is None:
            self._c_buf = (ctypes.c_ubyte * len(self._data)).from_buffer_copy(self._data)
        return self._c_buf

    @classmethod
    def from_file(cls, path):
        """Load bytecode from a .axbc file."""
        with open(path, "rb") as f:
            return cls(f.read())

    def save(self, path):
        """Save bytecode to a .axbc file."""
        with open(path, "wb") as f:
            f.write(self._data)

    @property
    def data(self):
        return self._data

    def __len__(self):
        return len(self._data)


# ---------------------------------------------------------------------------
# Main API class
# ---------------------------------------------------------------------------

class RuleDSL:
    """
    RuleDSL engine wrapper.

    Args:
        library_path: Path to ruledsl_capi.dll (.so on Linux).
                      If None, attempts auto-discovery in common locations.
    """

    # Locking discipline (see docs/thread_safety_model.md):
    #   Every method that reads self._compiler or calls through self._lib holds
    #   self._lock. _check_alive() is called with the lock already held.
    #
    # The lock is an RLock, not a Lock, because an on_trace callback fires from
    # INSIDE ax_eval_bytecode on the calling thread while the lock is held; a
    # plain Lock would deadlock a callback that re-enters the binding. But
    # reentrancy alone would make close() destroy the compiler from inside an
    # in-flight native call, so _in_native counts the native calls this
    # instance is currently inside, and close()/__del__ refuse to destroy
    # while it is non-zero.

    def __init__(self, library_path=None):
        # Establish the invariants first: a failure in _load_library below must
        # still leave close()/__del__ on well-defined state.
        self._lock = threading.RLock()
        self._in_native = 0
        self._lib = None
        self._compiler = None
        self._lib = self._load_library(library_path)
        self._setup_bindings()
        self._compiler = self._lib.ax_compiler_create()
        if not self._compiler:
            raise RuleDSLError(ErrorCode.RUNTIME, "Failed to create compiler instance")
        err = ctypes.create_string_buffer(1024)
        result = self._lib.ax_compiler_build(self._compiler, err, len(err))
        if not result:
            msg = err.value.decode("utf-8", errors="replace")
            self._lib.ax_compiler_destroy(self._compiler)
            self._compiler = None
            raise RuleDSLError(ErrorCode.COMPILE, f"Compiler build failed: {msg}")

    def __del__(self):
        # A finalizer must never block and never raise. If another thread holds
        # the lock, or this thread is inside a native call (GC can run from an
        # on_trace callback), skip destruction: a leaked compiler is reclaimed
        # at process exit, a use-after-free is not recoverable.
        lock = getattr(self, "_lock", None)
        if lock is None or not lock.acquire(False):
            return
        try:
            if getattr(self, "_in_native", 0):
                return
            compiler = getattr(self, "_compiler", None)
            lib = getattr(self, "_lib", None)
            if compiler and lib is not None:
                self._compiler = None
                lib.ax_compiler_destroy(compiler)
        except Exception:
            pass  # interpreter shutdown: raising here only prints noise
        finally:
            lock.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """Release the compiler. Idempotent and thread-safe.

        Blocks until any in-flight compile()/evaluate() on this instance has
        returned: destroying the compiler under a concurrent native call is a
        use-after-free the engine cannot see coming — it surfaces as a
        "successful" decision with empty output fields, or as a crash.

        Raises:
            RuleDSLError: If called from inside an in-flight engine call on
                this thread (e.g. from an on_trace callback). Destroying the
                compiler there would free it under the very call that is
                running. Close after evaluation returns.
        """
        with self._lock:
            if self._in_native:
                raise RuleDSLError(
                    ErrorCode.RUNTIME,
                    "close() called from inside an in-flight engine call "
                    "(e.g. an on_trace callback); destroying the compiler here "
                    "would be a use-after-free. Close after the call returns.")
            # Clear the field before destroying so no second path can free it.
            compiler, self._compiler = self._compiler, None
            if compiler and self._lib is not None:
                self._lib.ax_compiler_destroy(compiler)

    # -- Public API --------------------------------------------------------

    def compile(self, rule_source: str) -> Bytecode:
        """
        Compile rule source text to bytecode.

        Args:
            rule_source: RuleDSL source text (e.g., "rule r1 { when x > 1; then decline; }")

        Returns:
            Bytecode object that can be passed to evaluate() or saved to a file.

        Raises:
            CompileError: If the rule source has syntax or semantic errors.
            ArgumentError: If rule_source is not a str or contains a NUL byte.
        """
        # A NUL in the source would end the C string early: the compiler would
        # silently compile only the prefix while any hash taken over the file
        # attests to all of its bytes.
        if not isinstance(rule_source, str):
            raise ArgumentError(ErrorCode.INVALID_ARGUMENT,
                                "rule_source must be a str, got {0}".format(
                                    type(rule_source).__name__))
        if "\x00" in rule_source:
            raise ArgumentError(
                ErrorCode.INVALID_ARGUMENT,
                "rule_source contains a NUL byte at offset {0}; the compiler "
                "receives a NUL-terminated C string and would compile only the "
                "prefix".format(rule_source.index("\x00")))
        self._check_utf8("rule_source", rule_source)

        with self._lock:
            self._check_alive()
            self._in_native += 1
            try:
                bc = _AXBytecode()
                err = ctypes.create_string_buffer(2048)

                result = self._lib.ax_compile_to_bytecode(
                    self._compiler,
                    rule_source.encode("utf-8"),
                    ctypes.byref(bc),
                    err,
                    len(err),
                )

                # The free is in a finally covering EVERY exit after the call,
                # the compile-error return included: a partial-failure path
                # that still allocated would otherwise leak for the lifetime
                # of the process. Guarded on bc.data so an untouched struct is
                # never handed back to the allocator.
                try:
                    if not result:
                        msg = err.value.decode("utf-8", errors="replace")
                        detail = self._get_last_error_detail()
                        self._lib.ax_clear_last_error()
                        raise CompileError(ErrorCode.COMPILE, msg, detail)

                    # Copy bytes out before freeing the SDK allocation.
                    data = bytes(ctypes.cast(
                        bc.data, ctypes.POINTER(ctypes.c_ubyte * bc.size)).contents)
                finally:
                    if bc.data:
                        self._lib.ax_bytecode_free(ctypes.byref(bc))
            finally:
                self._in_native -= 1

        return Bytecode(data)

    def evaluate(self, bytecode: Bytecode, fields: dict,
                 now_utc_ms: float = None, on_trace=None) -> Decision:
        """
        Evaluate bytecode against input fields.

        Args:
            bytecode: Compiled Bytecode object or bytes.
            fields: Dict of field_name -> value. Values can be:
                    - float/int: NUMBER
                    - str: STRING
                    - bool: BOOL
                    - None: MISSING
            now_utc_ms: Epoch milliseconds for time-based rules. Must be supplied
                        explicitly (via this argument or as a "now_utc_ms" field);
                        the engine never reads the system clock — reproducibility
                        requires an explicit value. Omitting it for a time-based
                        rule raises EvalError (MISSING_NOW_UTC_MS).
            on_trace: Optional callable(str) invoked for each engine trace line.
                      The shipped evaluator emits one line per action assignment,
                      per decision, and per runtime error (see AXTraceCallback in
                      ruledsl_c.h). An exception raised inside on_trace never
                      crosses the C boundary: it is caught and re-raised after
                      evaluation completes.

        Returns:
            Decision object with matched, action, amount, currency, etc.

        Raises:
            EvalError: If evaluation fails.
        """
        # Build fields array
        # NOTE: now_utc_ms is NEVER auto-injected from the system clock. A deterministic
        # engine must be a pure function of explicit inputs; reading the wall clock here
        # would make the same bytecode+input non-reproducible. Time-based rules require
        # an explicit now_utc_ms (argument or field); otherwise the engine reports
        # MISSING_NOW_UTC_MS and this binding raises EvalError.
        if not isinstance(fields, dict):
            raise ArgumentError(ErrorCode.INVALID_ARGUMENT,
                                "fields must be a dict, got {0}".format(
                                    type(fields).__name__))
        # The clock has TWO documented entry points (the argument and a
        # "now_utc_ms" field), so both must pass the same check. Only the
        # argument used to be validated, which let a fractional, negative or
        # string clock through the field path and straight into evaluation.
        in_fields = "now_utc_ms" in fields
        if now_utc_ms is not None and in_fields:
            raise ArgumentError(
                ErrorCode.INVALID_ARGUMENT,
                "now_utc_ms was supplied both as an argument and as a field; "
                "one would silently overwrite the other. Supply exactly one.")
        all_fields = dict(fields)
        if now_utc_ms is not None:
            all_fields["now_utc_ms"] = self._check_now_utc_ms(now_utc_ms)
        elif in_fields:
            all_fields["now_utc_ms"] = self._check_now_utc_ms(fields["now_utc_ms"])

        # Everything below up to `with self._lock` touches no native state, so
        # it stays outside the critical section. (Bytecode._ctypes_buffer() is
        # lazy: two threads may each build a copy and one assignment wins. Both
        # copies are valid and each caller holds its own reference, so this is
        # not a correctness problem — do not "fix" it with the engine lock.)
        c_fields, field_refs = self._build_fields(all_fields)
        field_count = len(all_fields)

        # Prepare bytecode
        if isinstance(bytecode, Bytecode):
            bc_data = bytecode.data
        elif isinstance(bytecode, bytes):
            bc_data = bytecode
        else:
            raise ArgumentError(ErrorCode.INVALID_ARGUMENT,
                                "bytecode must be Bytecode or bytes")

        if isinstance(bytecode, Bytecode):
            c_bc_buf = bytecode._ctypes_buffer()
        else:
            c_bc_buf = (ctypes.c_ubyte * len(bc_data)).from_buffer_copy(bc_data)
        c_bc = _AXBytecode()
        c_bc.data = ctypes.cast(c_bc_buf, ctypes.POINTER(ctypes.c_ubyte))
        c_bc.size = len(bc_data)

        # Init options and decision
        opts = _AXEvalOptions()
        opts.struct_size = ctypes.sizeof(_AXEvalOptions)

        # trace_ref must stay referenced for the whole ax_eval_bytecode call —
        # ctypes does not keep the callback alive on its own.
        trace_ref = None
        trace_exc = []
        if on_trace is not None:
            def _trace_bridge(_user, line):
                try:
                    on_trace(line.decode("utf-8", errors="replace") if line else "")
                except BaseException as exc:
                    if not trace_exc:
                        trace_exc.append(exc)
            trace_ref = _AXTraceCallback(_trace_bridge)
            opts.trace_cb = trace_ref

        dec = _AXDecision()
        dec.struct_size = ctypes.sizeof(_AXDecision)

        err = ctypes.create_string_buffer(2048)

        with self._lock:
            self._check_alive()
            # _in_native marks the whole native region, not just the call: an
            # on_trace callback fires from inside ax_eval_bytecode on this
            # thread, and close() must refuse to run from there.
            self._in_native += 1
            try:
                code = self._lib.ax_eval_bytecode(
                    self._compiler,
                    ctypes.byref(c_bc),
                    c_fields,
                    field_count,
                    ctypes.byref(opts),
                    ctypes.byref(dec),
                    err,
                    len(err),
                )

                # From here on the engine owns the decision struct, so EVERY
                # exit resets it - including the engine's own error return
                # below, which used to skip the reset entirely. The guard
                # covers the whole post-call region, not just extraction.
                try:
                    if code != ErrorCode.OK:
                        msg = err.value.decode("utf-8", errors="replace")
                        detail = self._get_last_error_detail()
                        self._lib.ax_clear_last_error()
                        exc_cls = _ERROR_CLASS.get(code, EvalError)
                        raise exc_cls(code, msg, detail)

                    # Collect output fields assigned in THEN clauses.
                    # The lock is load-bearing for CORRECTNESS here, not merely
                    # defensive: ax_eval_output_field_count/at read
                    # compiler-GLOBAL state that the next ax_eval_bytecode
                    # overwrites, so the read must happen in the same critical
                    # section as the evaluation.
                    outputs = {}
                    count = self._lib.ax_eval_output_field_count(self._compiler)
                    for i in range(count):
                        out_name = ctypes.c_char_p()
                        out_value = _AXValue()
                        rc = self._lib.ax_eval_output_field_at(
                            self._compiler, i,
                            ctypes.byref(out_name), ctypes.byref(out_value),
                        )
                        if rc == ErrorCode.OK and out_name.value:
                            name_str = self._decode_result("output field name",
                                                           out_name.value)
                            if out_value.type == _VALUE_NUMBER:
                                outputs[name_str] = out_value.number
                            elif out_value.type == _VALUE_STRING or out_value.type == _VALUE_IDENT:
                                outputs[name_str] = self._decode_result(
                                    "output field '%s'" % name_str,
                                    out_value.text) if out_value.text else ""
                            elif out_value.type == _VALUE_BOOL:
                                outputs[name_str] = bool(out_value.boolean)
                            else:
                                outputs[name_str] = None

                    # Extract decision before reset
                    result = Decision(
                        matched=dec.matched,
                        action_type=dec.action_type,
                        amount=dec.amount,
                        currency=self._decode_result("currency", dec.currency)
                        if dec.currency else None,
                        window_count=dec.window_count,
                        window_unit=self._decode_result("window_unit", dec.window_unit)
                        if dec.window_unit else None,
                        rule_name=self._decode_result("rule_name", dec.rule_name)
                        if dec.rule_name else None,
                        outputs=outputs,
                    )
                finally:
                    # In a finally: a decode failure above must still release
                    # the native decision, and the next evaluation must not
                    # inherit this one's state.
                    self._lib.ax_decision_reset(ctypes.byref(dec))
            finally:
                self._in_native -= 1

        if trace_exc:
            raise trace_exc[0]
        return result

    def check_compatibility(self, bytecode) -> dict:
        """
        Check bytecode compatibility with the current engine.

        Returns:
            Dict with keys: compatible (bool), axbc_version, lang_major, lang_minor,
            minimum_engine_abi, status, status_name.
        """
        if isinstance(bytecode, Bytecode):
            bc_data = bytecode.data
        elif isinstance(bytecode, bytes):
            bc_data = bytecode
        else:
            raise ArgumentError(ErrorCode.INVALID_ARGUMENT,
                                "bytecode must be Bytecode or bytes")

        info = _AXCompatibilityInfo()
        info.struct_size = ctypes.sizeof(_AXCompatibilityInfo)

        if isinstance(bytecode, Bytecode):
            buf = bytecode._ctypes_buffer()
        else:
            buf = (ctypes.c_ubyte * len(bc_data)).from_buffer_copy(bc_data)
        # ax_check_bytecode_compatibility takes no compiler handle, but it does
        # go through self._lib: locking makes "called after close()" the stable
        # AX_ERR_RUNTIME instead of an AttributeError on a torn-down instance.
        with self._lock:
            self._check_alive()
            status = self._lib.ax_check_bytecode_compatibility(
                buf, len(bc_data), ctypes.byref(info)
            )

        status_names = {0: "OK", 1: "INVALID_ARGUMENT", 2: "BAD_STRUCT_SIZE",
                        6: "STRUCTURALLY_INVALID", 7: "UNSUPPORTED_VERSION",
                        8: "CORRUPTED_PAYLOAD"}

        return {
            "compatible": status == 0,
            "axbc_version": info.axbc_version,
            "lang_major": info.lang_major,
            "lang_minor": info.lang_minor,
            "minimum_engine_abi": info.minimum_engine_abi,
            "status": status,
            "status_name": status_names.get(status, f"UNKNOWN({status})"),
        }

    def version(self) -> str:
        """Return the engine version string.

        Raises:
            RuleDSLError: If the engine has been closed.
        """
        with self._lock:
            self._check_alive()
            v = self._lib.ax_version_string()
        return v.decode("utf-8") if v else "unknown"

    # -- Internal ----------------------------------------------------------

    def _check_alive(self):
        """Callers MUST hold self._lock; the check is only meaningful while
        the compiler cannot be destroyed underneath it."""
        if not self._compiler:
            raise RuleDSLError(ErrorCode.RUNTIME, "Compiler has been closed")

    @staticmethod
    def _decode_result(what, raw):
        """Decode engine-produced DECISION text strictly.

        No errors="replace" here on purpose. Replacement would put U+FFFD into
        a decision the caller then records, so the record would describe a
        result the engine never produced — the output-side twin of the
        input-side fidelity rule. Diagnostics (error text, trace lines) do use
        replacement: they are prose about a failure, not decision data.

        A raw UnicodeDecodeError is not part of this binding's contract, so it
        becomes a typed RuleDSLError naming the field that could not be read.
        """
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuleDSLError(
                ErrorCode.RUNTIME,
                "engine returned {0} as invalid UTF-8 ({1}); refusing to "
                "substitute replacement characters into a decision".format(
                    what, exc.reason))

    def _get_last_error_detail(self):
        buf = ctypes.create_string_buffer(1024)
        self._lib.ax_last_error_detail_utf8(buf, len(buf))
        return buf.value.decode("utf-8", errors="replace")

    @staticmethod
    def _brief(value):
        """Bounded repr for an error message.

        Two reasons this exists. An unbounded one lets a caller inflate the
        exception with the very input being rejected; and formatting a huge
        int as a float (the old "{:.0f}".format(float(value))) raises
        OverflowError for something like 10**400, replacing the typed error
        with an untyped one at the exact moment the guard fires.
        """
        # repr() is not safe to call first. CPython caps int->str conversion
        # (sys.set_int_max_str_digits, 4300 by default), so repr(10**5000)
        # raises ValueError - an untyped error thrown while building the
        # message for a typed one. Same for an enormous str: formatting a
        # 1 MiB field name only to slice it is wasted work at best.
        if isinstance(value, int) and not isinstance(value, bool):
            if value.bit_length() > 256:
                return "an integer of about %d bits" % value.bit_length()
        elif isinstance(value, str) and len(value) > 64:
            return repr(value[:64]) + "...(truncated)"
        text = repr(value)
        return text if len(text) <= 64 else text[:64] + "...(truncated)"

    @staticmethod
    def _check_utf8(what, text):
        """Reject text the engine cannot receive as UTF-8.

        A lone surrogate ("\\ud800") is a legal Python str and an illegal
        UTF-8 sequence, so .encode() raises UnicodeEncodeError. Left alone it
        escapes as an untyped exception from the middle of _build_fields,
        after the array has already been partially populated. Encoding with
        errors="replace" would be worse: the engine would silently evaluate
        U+FFFD while the caller — and any log alongside it — believed
        otherwise.
        """
        try:
            text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ArgumentError(
                ErrorCode.INVALID_ARGUMENT,
                "{0} is not encodable as UTF-8 ({1}); the engine receives "
                "UTF-8 bytes and this string has no faithful "
                "representation".format(what, exc.reason))

    @staticmethod
    def _check_field(name, value):
        """Reject anything the engine cannot receive faithfully.

        The engine sees fields as AXValue: a double, a NUL-terminated C string,
        a bool, or missing. Values that survive that boundary only partially
        are refused here rather than silently altered, because a partially
        transmitted value makes the binding — and anything logging alongside it
        — report an input the engine never evaluated.

        Raises:
            ArgumentError: Bad field name, embedded NUL, unsafe integer,
                un-encodable text, or an unsupported type.
            EvalError: Non-finite float (AX_ERR_NON_FINITE).
        """
        if not isinstance(name, str) or not name:
            raise ArgumentError(
                ErrorCode.INVALID_ARGUMENT,
                "Field names must be non-empty strings, got "
                "{0} ({1})".format(RuleDSL._brief(name), type(name).__name__))
        if "\x00" in name:
            raise ArgumentError(
                ErrorCode.INVALID_ARGUMENT,
                "Field name {0} contains a NUL byte; the engine receives a "
                "NUL-terminated C string and would see only the prefix".format(
                    RuleDSL._brief(name)))
        RuleDSL._check_utf8("Field name {0}".format(RuleDSL._brief(name)), name)

        # Every message below renders the name through _brief. A field name is
        # caller-supplied and unbounded, and a VALID one reaches these paths -
        # the guards above only bound names that are themselves malformed, so
        # a 1 MiB name with a bad VALUE produced a 1 MiB exception.
        brief_name = RuleDSL._brief(name)

        if value is None or isinstance(value, bool):
            return
        if isinstance(value, int):
            if value > MAX_SAFE_INTEGER or value < -MAX_SAFE_INTEGER:
                raise ArgumentError(
                    ErrorCode.INVALID_ARGUMENT,
                    "Field {0}: integer {1} is not exactly representable as "
                    "float64 (|value| > 2**53-1); the engine would evaluate a "
                    "different number. Pass identifiers as strings.".format(
                        brief_name, RuleDSL._brief(value)))
            return
        if isinstance(value, float):
            if not math.isfinite(value):
                raise EvalError(
                    ErrorCode.NON_FINITE,
                    "Field {0}: {1} is not a finite number".format(
                        brief_name, value))
            return
        if isinstance(value, str):
            if "\x00" in value:
                raise ArgumentError(
                    ErrorCode.INVALID_ARGUMENT,
                    "Field {0}: string contains a NUL byte; the engine "
                    "receives a NUL-terminated C string and would see only the "
                    "prefix".format(brief_name))
            RuleDSL._check_utf8(
                "Field {0}: string value".format(brief_name), value)
            return
        raise ArgumentError(
            ErrorCode.INVALID_ARGUMENT,
            "Unsupported field type for {0}: {1}. "
            "Use float, int, str, bool, or None.".format(
                brief_name, type(value).__name__))

    @staticmethod
    def _check_now_utc_ms(value):
        """Validate the explicit clock and return it as a float.

        now_utc_ms is epoch MILLISECONDS: an integer. Previously this was a
        bare float(value), which accepted a numeric string and silently
        rounded an out-of-range integer.

        Raises:
            EvalError: Not a number (AX_ERR_NOW_UTC_MS_NOT_NUMBER) or not
                finite (AX_ERR_NON_FINITE).
            ArgumentError: Numeric but not an exact whole millisecond at or
                after the epoch.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EvalError(
                ErrorCode.NOW_UTC_MS_NOT_NUMBER,
                "now_utc_ms must be a number, got {0}".format(type(value).__name__))
        if isinstance(value, float):
            if not math.isfinite(value):
                raise EvalError(
                    ErrorCode.NON_FINITE,
                    "now_utc_ms must be finite, got {0}".format(value))
            if not value.is_integer():
                raise ArgumentError(
                    ErrorCode.INVALID_ARGUMENT,
                    "now_utc_ms is epoch milliseconds and must be a whole "
                    "number, got {0}".format(RuleDSL._brief(value)))
        if value > MAX_SAFE_INTEGER:
            raise ArgumentError(
                ErrorCode.INVALID_ARGUMENT,
                "now_utc_ms {0} is outside the exactly representable range "
                "(value > 2**53-1)".format(RuleDSL._brief(value)))
        # Epoch milliseconds are counted from 1970; a negative value is a unit
        # or sign mistake far more often than a deliberate pre-1970 timestamp,
        # and the MCP server advertises minimum 0. Both layers agree.
        if value < 0:
            raise ArgumentError(
                ErrorCode.INVALID_ARGUMENT,
                "now_utc_ms {0} is negative; epoch milliseconds start at "
                "0 (1970-01-01T00:00:00Z)".format(RuleDSL._brief(value)))
        return float(value)

    @staticmethod
    def _build_fields(fields_dict):
        """Convert a Python dict to a ctypes AXField array.

        Validate-then-build: every pair is checked before the array is touched,
        so a bad value never leaves a half-populated array behind.
        """
        for name, value in fields_dict.items():
            RuleDSL._check_field(name, value)

        n = len(fields_dict)
        arr = (_AXField * n)()
        refs = []  # prevent GC of encoded strings

        for i, (name, value) in enumerate(fields_dict.items()):
            name_b = name.encode("utf-8")
            refs.append(name_b)
            arr[i].name = name_b

            if value is None:
                arr[i].value.type = _VALUE_MISSING
            elif isinstance(value, bool):
                arr[i].value.type = _VALUE_BOOL
                arr[i].value.boolean = 1 if value else 0
            elif isinstance(value, (int, float)):
                arr[i].value.type = _VALUE_NUMBER
                arr[i].value.number = float(value)
            else:  # str; _check_field has already rejected everything else
                val_b = value.encode("utf-8")
                refs.append(val_b)
                arr[i].value.type = _VALUE_STRING
                arr[i].value.text = val_b

        return arr, refs

    @staticmethod
    def _load_library(path):
        """Load the shared library."""
        if path:
            resolved = Path(path).resolve()
            if resolved.exists():
                return ctypes.CDLL(str(resolved))
            return ctypes.CDLL(str(path))

        # Auto-discovery
        candidates = []
        if platform.system() == "Windows":
            candidates = [
                "ruledsl_capi.dll",
                "bin/ruledsl_capi.dll",
                "../bin/ruledsl_capi.dll",
            ]
        else:
            candidates = [
                "libruledsl_capi.so",
                "bin/libruledsl_capi.so",
                "../bin/libruledsl_capi.so",
            ]

        for c in candidates:
            try:
                return ctypes.CDLL(c)
            except OSError:
                continue

        hint = "ruledsl_capi.dll" if platform.system() == "Windows" else "libruledsl_capi.so"
        raise FileNotFoundError(
            f"Could not find RuleDSL library. "
            f"Pass the path explicitly: RuleDSL('{hint}')"
        )

    def _setup_bindings(self):
        """Declare ctypes function signatures."""
        L = self._lib

        L.ax_compiler_create.restype = ctypes.c_void_p
        L.ax_compiler_create.argtypes = []

        L.ax_compiler_destroy.restype = None
        L.ax_compiler_destroy.argtypes = [ctypes.c_void_p]

        L.ax_compiler_build.restype = ctypes.c_int
        L.ax_compiler_build.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]

        L.ax_compile_to_bytecode.restype = ctypes.c_int
        L.ax_compile_to_bytecode.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p,
            ctypes.POINTER(_AXBytecode), ctypes.c_char_p, ctypes.c_size_t,
        ]

        L.ax_eval_bytecode.restype = ctypes.c_int
        L.ax_eval_bytecode.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(_AXBytecode),
            ctypes.POINTER(_AXField), ctypes.c_uint32,
            ctypes.POINTER(_AXEvalOptions), ctypes.POINTER(_AXDecision),
            ctypes.c_char_p, ctypes.c_size_t,
        ]

        L.ax_check_bytecode_compatibility.restype = ctypes.c_int
        L.ax_check_bytecode_compatibility.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(_AXCompatibilityInfo),
        ]

        L.ax_bytecode_free.restype = None
        L.ax_bytecode_free.argtypes = [ctypes.POINTER(_AXBytecode)]

        L.ax_decision_reset.restype = None
        L.ax_decision_reset.argtypes = [ctypes.POINTER(_AXDecision)]

        L.ax_free.restype = None
        L.ax_free.argtypes = [ctypes.c_void_p]

        L.ax_version_string.restype = ctypes.c_char_p
        L.ax_version_string.argtypes = []

        L.ax_error_to_string.restype = ctypes.c_char_p
        L.ax_error_to_string.argtypes = [ctypes.c_int]

        L.ax_last_error_code.restype = ctypes.c_int
        L.ax_last_error_code.argtypes = []

        L.ax_last_error_detail_utf8.restype = ctypes.c_size_t
        L.ax_last_error_detail_utf8.argtypes = [ctypes.c_char_p, ctypes.c_size_t]

        L.ax_clear_last_error.restype = None
        L.ax_clear_last_error.argtypes = []

        L.ax_eval_output_field_count.restype = ctypes.c_uint32
        L.ax_eval_output_field_count.argtypes = [ctypes.c_void_p]

        L.ax_eval_output_field_at.restype = ctypes.c_int
        L.ax_eval_output_field_at.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(_AXValue),
        ]
