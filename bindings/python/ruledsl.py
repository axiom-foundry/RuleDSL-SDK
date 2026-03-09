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
import os
import platform
import time
from pathlib import Path


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
    ErrorCode.COMPILE: CompileError,
    ErrorCode.VERIFY: VerifyError,
    ErrorCode.INVALID_ARGUMENT: ArgumentError,
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


class _AXEvalOptions(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("trace_cb", ctypes.c_void_p),
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

    __slots__ = ("_data",)

    def __init__(self, data: bytes):
        self._data = data

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

    def __init__(self, library_path=None):
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
        if hasattr(self, "_compiler") and self._compiler:
            self._lib.ax_compiler_destroy(self._compiler)
            self._compiler = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """Release the compiler. Safe to call multiple times."""
        if self._compiler:
            self._lib.ax_compiler_destroy(self._compiler)
            self._compiler = None

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
        """
        self._check_alive()
        bc = _AXBytecode()
        err = ctypes.create_string_buffer(2048)

        result = self._lib.ax_compile_to_bytecode(
            self._compiler,
            rule_source.encode("utf-8"),
            ctypes.byref(bc),
            err,
            len(err),
        )

        if not result:
            msg = err.value.decode("utf-8", errors="replace")
            detail = self._get_last_error_detail()
            self._lib.ax_clear_last_error()
            raise CompileError(ErrorCode.COMPILE, msg, detail)

        # Copy bytes out before freeing the SDK allocation
        data = bytes(ctypes.cast(bc.data, ctypes.POINTER(ctypes.c_ubyte * bc.size)).contents)
        self._lib.ax_bytecode_free(ctypes.byref(bc))

        return Bytecode(data)

    def evaluate(self, bytecode: Bytecode, fields: dict,
                 now_utc_ms: float = None) -> Decision:
        """
        Evaluate bytecode against input fields.

        Args:
            bytecode: Compiled Bytecode object or bytes.
            fields: Dict of field_name -> value. Values can be:
                    - float/int: NUMBER
                    - str: STRING
                    - bool: BOOL
                    - None: MISSING
            now_utc_ms: Epoch milliseconds for time-based rules.
                        If None, uses current system time automatically.

        Returns:
            Decision object with matched, action, amount, currency, etc.

        Raises:
            EvalError: If evaluation fails.
        """
        self._check_alive()

        # Auto-inject now_utc_ms if not provided
        if now_utc_ms is None and "now_utc_ms" not in fields:
            now_utc_ms = time.time() * 1000.0

        # Build fields array
        all_fields = dict(fields)
        if now_utc_ms is not None:
            all_fields["now_utc_ms"] = float(now_utc_ms)

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

        c_bc = _AXBytecode()
        c_bc_buf = (ctypes.c_ubyte * len(bc_data))(*bc_data)
        c_bc.data = ctypes.cast(c_bc_buf, ctypes.POINTER(ctypes.c_ubyte))
        c_bc.size = len(bc_data)

        # Init options and decision
        opts = _AXEvalOptions()
        opts.struct_size = ctypes.sizeof(_AXEvalOptions)

        dec = _AXDecision()
        dec.struct_size = ctypes.sizeof(_AXDecision)

        err = ctypes.create_string_buffer(2048)

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

        if code != ErrorCode.OK:
            msg = err.value.decode("utf-8", errors="replace")
            detail = self._get_last_error_detail()
            self._lib.ax_clear_last_error()
            exc_cls = _ERROR_CLASS.get(code, EvalError)
            raise exc_cls(code, msg, detail)

        # Collect output fields assigned in THEN clauses
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
                name_str = out_name.value.decode("utf-8")
                if out_value.type == _VALUE_NUMBER:
                    outputs[name_str] = out_value.number
                elif out_value.type == _VALUE_STRING or out_value.type == _VALUE_IDENT:
                    outputs[name_str] = out_value.text.decode("utf-8") if out_value.text else ""
                elif out_value.type == _VALUE_BOOL:
                    outputs[name_str] = bool(out_value.boolean)
                else:
                    outputs[name_str] = None

        # Extract decision before reset
        result = Decision(
            matched=dec.matched,
            action_type=dec.action_type,
            amount=dec.amount,
            currency=dec.currency.decode("utf-8") if dec.currency else None,
            window_count=dec.window_count,
            window_unit=dec.window_unit.decode("utf-8") if dec.window_unit else None,
            rule_name=dec.rule_name.decode("utf-8") if dec.rule_name else None,
            outputs=outputs,
        )

        self._lib.ax_decision_reset(ctypes.byref(dec))
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

        buf = (ctypes.c_ubyte * len(bc_data))(*bc_data)
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
        """Return the engine version string."""
        v = self._lib.ax_version_string()
        return v.decode("utf-8") if v else "unknown"

    # -- Internal ----------------------------------------------------------

    def _check_alive(self):
        if not self._compiler:
            raise RuleDSLError(ErrorCode.RUNTIME, "Compiler has been closed")

    def _get_last_error_detail(self):
        buf = ctypes.create_string_buffer(1024)
        self._lib.ax_last_error_detail_utf8(buf, len(buf))
        return buf.value.decode("utf-8", errors="replace")

    @staticmethod
    def _build_fields(fields_dict):
        """Convert a Python dict to a ctypes AXField array."""
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
            elif isinstance(value, str):
                val_b = value.encode("utf-8")
                refs.append(val_b)
                arr[i].value.type = _VALUE_STRING
                arr[i].value.text = val_b
            else:
                raise ArgumentError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"Unsupported field type for '{name}': {type(value).__name__}. "
                    f"Use float, str, bool, or None."
                )

        return arr, refs

    @staticmethod
    def _load_library(path):
        """Load the shared library."""
        if path:
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
                "lib/libruledsl_capi.so",
                "../lib/libruledsl_capi.so",
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
