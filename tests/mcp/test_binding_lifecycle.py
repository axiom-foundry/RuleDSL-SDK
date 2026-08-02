"""RuleDSL Python binding lifecycle and value-fidelity tests.

Covers the binding's two safety properties, both of which failed silently
before and both of which are invisible to a single-threaded happy path:

  1. Lifetime. Destroying the compiler while another thread (or the same
     thread, via an on_trace callback) is inside a native call is a
     use-after-free. It does not crash loudly: an independent audit observed
     20/20 concurrent evaluations returning a "successful" ALLOW whose output
     fields were silently {}. close() must either wait or refuse, and every
     outcome must be either a correct Decision or a stable AX_ERR_RUNTIME.

  2. Value fidelity. A value that reaches the engine altered (NUL-truncated
     string, integer rounded past 2**53) makes the binding report an input
     the engine never evaluated. Those are rejected, not adjusted.

Requires the engine DLL and the public SDK python wrapper:
  RULEDSL_DLL      (default: <repo>/build/Release/ruledsl_capi.dll)
  RULEDSL_WRAPPER  (default: <repo>/../RuleDSL-SDK/bindings/python)
"""

import gc
import io
import os
import sys
import threading
from contextlib import redirect_stderr
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

DLL_PATH = os.environ.get(
    "RULEDSL_DLL", str(REPO_ROOT / "build" / "Release" / "ruledsl_capi.dll"))
WRAPPER_DIR = os.environ.get(
    "RULEDSL_WRAPPER", str(REPO_ROOT.parent / "RuleDSL-SDK" / "bindings" / "python"))
sys.path.insert(0, WRAPPER_DIR)
from ruledsl import (  # noqa: E402
    MAX_SAFE_INTEGER,
    ArgumentError,
    CompileError,
    Decision,
    EvalError,
    RuleDSL,
    RuleDSLError,
)

# ---------------------------------------------------------------------------
# Test infrastructure (same harness style as the other tests/mcp modules)
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0
_errors = []


def test(name):
    def decorator(fn):
        global _passed, _failed
        try:
            fn()
            _passed += 1
            print(f"  PASS  {name}")
        except Exception as e:
            _failed += 1
            _errors.append((name, e))
            print(f"  FAIL  {name}: {e}")
        return fn
    return decorator


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(msg or "condition is false")


def assert_eq(a, b, msg=""):
    if a != b:
        raise AssertionError(f"Expected {b!r}, got {a!r}" + (f" ({msg})" if msg else ""))


def assert_raises(exc_type, fn, code_name=None, contains=()):
    try:
        fn()
    except exc_type as e:
        if code_name is not None and getattr(e, "code_name", None) != code_name:
            raise AssertionError(
                f"Expected code_name {code_name}, got {getattr(e, 'code_name', None)}: {e}")
        for fragment in contains:
            if fragment not in str(e):
                raise AssertionError(f"{exc_type.__name__} message missing {fragment!r}: {e}")
        return e
    raise AssertionError(f"{exc_type.__name__} not raised")


NOW = 1700000000000

# block_extreme fires above 25000 and assigns two output fields; the
# per-thread rules below derive risk_score from the thread's own amount, which
# is what makes cross-contamination detectable.
RULE_SOURCE = (REPO_ROOT / "rules" / "velocity_limits.ruledsl.txt").read_text(
    encoding="utf-8")

EXTREME_OUTPUTS = {"reason": "extreme_amount", "risk_score": 99.0}

VALID_INNER_RULE = "rule inner { when amount > 1; then allow; }"


def new_engine():
    return RuleDSL(DLL_PATH)


engine = new_engine()
BYTECODE = engine.compile(RULE_SOURCE)


# ---------------------------------------------------------------------------
# Idempotence and post-close behaviour
# ---------------------------------------------------------------------------

@test("close: idempotent, and the context manager closes")
def _():
    e = new_engine()
    e.close()
    e.close()  # must be a no-op, not a double free
    with new_engine() as ctx:
        assert_true(ctx.evaluate(BYTECODE, {"amount": 30000.0}, now_utc_ms=NOW).matched)
    assert_raises(RuleDSLError, lambda: ctx.version(), code_name="AX_ERR_RUNTIME")


@test("after close: every public call raises AX_ERR_RUNTIME, not AttributeError")
def _():
    e = new_engine()
    e.close()
    # version() and check_compatibility() used to touch self._lib with no lock
    # and no liveness check at all.
    assert_raises(RuleDSLError, lambda: e.version(), code_name="AX_ERR_RUNTIME")
    assert_raises(RuleDSLError, lambda: e.check_compatibility(BYTECODE),
                  code_name="AX_ERR_RUNTIME")
    assert_raises(RuleDSLError, lambda: e.compile(RULE_SOURCE),
                  code_name="AX_ERR_RUNTIME")
    assert_raises(RuleDSLError,
                  lambda: e.evaluate(BYTECODE, {"amount": 1.0}, now_utc_ms=NOW),
                  code_name="AX_ERR_RUNTIME")


@test("partial init: a failed constructor leaves close()/__del__ well-defined")
def _():
    # __init__ must establish _lib/_compiler/_in_native BEFORE _load_library
    # can fail, or close() raises AttributeError on the half-built instance.
    stderr = io.StringIO()
    with redirect_stderr(stderr):
        try:
            new = RuleDSL("no_such_library_ruledsl_capi")
        except Exception:
            new = None
        del new
        gc.collect()
    assert_eq(stderr.getvalue(), "", "finalizer printed 'Exception ignored in __del__'")

    half = RuleDSL.__new__(RuleDSL)
    half._lock = threading.RLock()
    half._in_native = 0
    half._lib = None
    half._compiler = None
    half.close()  # no AttributeError on self._lib


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

@test("race: concurrent close() never yields a 'successful' empty-output decision")
def _():
    # The regression this file exists for. Before the fix, close() did not take
    # the lock and evaluate() checked liveness outside it, so a close landing in
    # that window freed the compiler under an in-flight ax_eval_bytecode. The
    # observed signature was not a crash: evaluation "succeeded" with ALLOW and
    # outputs == {}. Any such outcome is a hard failure here.
    #
    # A genuine use-after-free may instead abort the process; a non-zero exit is
    # the intended CI signal for that.
    for _round in range(50):
        e = new_engine()
        bc = e.compile(RULE_SOURCE)
        barrier = threading.Barrier(2)
        outcomes = []

        def worker():
            barrier.wait()
            for _ in range(20):
                try:
                    outcomes.append(e.evaluate(bc, {"amount": 30000.0}, now_utc_ms=NOW))
                except RuleDSLError as exc:
                    outcomes.append(exc)
                    return

        t = threading.Thread(target=worker)
        t.start()
        barrier.wait()
        e.close()
        t.join(timeout=30)
        assert_true(not t.is_alive(), "worker did not finish: close() deadlocked")

        for outcome in outcomes:
            if isinstance(outcome, RuleDSLError):
                assert_eq(outcome.code_name, "AX_ERR_RUNTIME",
                          "unexpected error during concurrent close")
                continue
            assert_true(isinstance(outcome, Decision), f"unexpected outcome {outcome!r}")
            assert_eq(outcome.rule_name, "block_extreme")
            assert_eq(outcome.outputs, EXTREME_OUTPUTS,
                      "successful decision with silently dropped output fields "
                      "- the use-after-free signature")


@test("race: concurrent evaluations do not cross-contaminate output fields")
def _():
    # ax_eval_output_field_count/at read compiler-GLOBAL state that the next
    # ax_eval_bytecode overwrites, so the read has to be in the same critical
    # section as the evaluation. Eight threads, eight distinct amounts, each
    # asserting the risk_score derived from its OWN input.
    #
    # medium_hourly_cap: 1000 < amount <= 5000, risk_score = (amount / 1000) * 10
    amounts = [1100.0 + 100.0 * i for i in range(8)]
    results = {}
    errors = []
    start = threading.Barrier(len(amounts))

    def worker(amount):
        try:
            start.wait()
            for _ in range(25):
                d = engine.evaluate(BYTECODE, {"amount": amount}, now_utc_ms=NOW)
                if d.outputs.get("risk_score") != (amount / 1000.0) * 10:
                    errors.append((amount, d.outputs))
                    return
            results[amount] = True
        except Exception as exc:  # noqa: BLE001 - reported below
            errors.append((amount, exc))

    threads = [threading.Thread(target=worker, args=(a,)) for a in amounts]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert_eq(errors, [], "output fields crossed between concurrent evaluations")
    assert_eq(len(results), len(amounts))


@test("race: version()/check_compatibility() are safe alongside evaluations")
def _():
    errors = []
    stop = threading.Event()

    def reader():
        try:
            while not stop.is_set():
                assert_true(bool(engine.version()))
                assert_true(engine.check_compatibility(BYTECODE)["compatible"])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    readers = [threading.Thread(target=reader) for _ in range(4)]
    for t in readers:
        t.start()
    try:
        for _ in range(100):
            engine.evaluate(BYTECODE, {"amount": 30000.0}, now_utc_ms=NOW)
    finally:
        stop.set()
        for t in readers:
            t.join(timeout=30)
    assert_eq(errors, [])


# ---------------------------------------------------------------------------
# Reentrancy (acceptance criterion K1)
# ---------------------------------------------------------------------------

@test("reentrancy: close() from inside on_trace is refused, engine survives")
def _():
    # The lock is an RLock so an on_trace callback can re-enter the binding
    # without deadlocking. That reentrancy would otherwise let close() destroy
    # the compiler from inside the very ax_eval_bytecode call that is running,
    # so _in_native must make close() refuse there.
    e = new_engine()
    bc = e.compile(RULE_SOURCE)
    lines = []

    def cb(line):
        lines.append(line)
        e.close()

    exc = assert_raises(
        RuleDSLError,
        lambda: e.evaluate(bc, {"amount": 30000.0}, now_utc_ms=NOW, on_trace=cb),
        code_name="AX_ERR_RUNTIME",
        contains=("in-flight",))
    assert_true("close()" in str(exc))
    assert_true(lines, "on_trace never fired, so the reentrant path was not exercised")

    # The engine must be intact: the compiler was NOT destroyed.
    d = e.evaluate(bc, {"amount": 30000.0}, now_utc_ms=NOW)
    assert_eq(d.rule_name, "block_extreme")
    assert_eq(d.outputs, EXTREME_OUTPUTS)
    e.close()


@test("reentrancy: compile() from inside on_trace does not corrupt the engine")
def _():
    e = new_engine()
    bc = e.compile(RULE_SOURCE)
    inner = []

    def cb(line):
        if inner:
            return
        try:
            e.compile(VALID_INNER_RULE)
            inner.append("ok")
        except RuleDSLError as exc:
            inner.append(exc.code_name)

    e.evaluate(bc, {"amount": 30000.0}, now_utc_ms=NOW, on_trace=cb)
    assert_true(inner, "on_trace never fired")
    # Either outcome is acceptable: the engine may serve the nested compile, or
    # report its own AX_ERR_CONCURRENT_COMPILER_USE. What must NOT happen is a
    # deadlock (a plain Lock) or a corrupted engine.
    d = e.evaluate(bc, {"amount": 30000.0}, now_utc_ms=NOW)
    assert_eq(d.outputs, EXTREME_OUTPUTS)
    e.close()


# ---------------------------------------------------------------------------
# Value fidelity
# ---------------------------------------------------------------------------

@test("fidelity: a string containing NUL is refused, not silently truncated")
def _():
    # An audit passed {"country": "TR\x00KP"}: the record kept the whole string
    # while the engine matched a rule on "TR".
    exc = assert_raises(
        ArgumentError,
        lambda: engine.evaluate(BYTECODE, {"amount": 100.0, "country": "TR\x00KP"},
                                now_utc_ms=NOW),
        code_name="AX_ERR_INVALID_ARGUMENT",
        contains=("NUL",))
    assert_true("country" in str(exc))


@test("fidelity: an integer beyond 2**53-1 is refused, not silently rounded")
def _():
    # 9007199254740993 was logged verbatim while the engine evaluated
    # 9007199254740992.
    assert_raises(
        ArgumentError,
        lambda: engine.evaluate(BYTECODE, {"amount": 100.0, "account": 2 ** 53 + 1},
                                now_utc_ms=NOW),
        code_name="AX_ERR_INVALID_ARGUMENT")
    assert_raises(
        ArgumentError,
        lambda: engine.evaluate(BYTECODE, {"amount": 100.0, "account": -(2 ** 53 + 1)},
                                now_utc_ms=NOW),
        code_name="AX_ERR_INVALID_ARGUMENT")
    # The boundary itself is exactly representable and must be accepted.
    engine.evaluate(BYTECODE, {"amount": 100.0, "account": MAX_SAFE_INTEGER},
                    now_utc_ms=NOW)
    engine.evaluate(BYTECODE, {"amount": 100.0, "account": -MAX_SAFE_INTEGER},
                    now_utc_ms=NOW)


@test("fidelity: non-finite floats report AX_ERR_NON_FINITE")
def _():
    for value in (float("nan"), float("inf"), float("-inf")):
        assert_raises(
            EvalError,
            lambda v=value: engine.evaluate(BYTECODE, {"amount": v}, now_utc_ms=NOW),
            code_name="AX_ERR_NON_FINITE")


@test("fidelity: unsupported and malformed field entries are refused")
def _():
    for value in ({"a": 1}, [1, 2], (1,), b"x"):
        assert_raises(
            ArgumentError,
            lambda v=value: engine.evaluate(BYTECODE, {"amount": 1.0, "x": v},
                                            now_utc_ms=NOW),
            code_name="AX_ERR_INVALID_ARGUMENT")
    for name in ("", "a\x00b", 123):
        assert_raises(
            ArgumentError,
            lambda n=name: engine.evaluate(BYTECODE, {n: 1.0}, now_utc_ms=NOW),
            code_name="AX_ERR_INVALID_ARGUMENT")
    assert_raises(
        ArgumentError,
        lambda: engine.evaluate(BYTECODE, ["not", "a", "dict"], now_utc_ms=NOW),
        code_name="AX_ERR_INVALID_ARGUMENT")


@test("fidelity: nothing is half-built when a later field is rejected")
def _():
    # _build_fields validates every pair before touching the ctypes array, so a
    # rejection at index 5 cannot leave a partially populated array behind.
    fields = {f"f{i}": float(i) for i in range(5)}
    fields["bad"] = float("nan")
    fields["amount"] = 30000.0
    assert_raises(EvalError, lambda: engine.evaluate(BYTECODE, fields, now_utc_ms=NOW),
                  code_name="AX_ERR_NON_FINITE")
    # The engine is unaffected by the refused call.
    d = engine.evaluate(BYTECODE, {"amount": 30000.0}, now_utc_ms=NOW)
    assert_eq(d.outputs, EXTREME_OUTPUTS)


# One corpus, driven through BOTH documented clock entry points. The docstring
# of evaluate() has always said now_utc_ms may arrive "via this argument or as
# a now_utc_ms field", but only the argument was ever checked - so the field
# path accepted a fractional, negative or string clock and passed it straight
# into evaluation.
NOW_REJECTS = (
    ("1700000000000", EvalError, "AX_ERR_NOW_UTC_MS_NOT_NUMBER"),
    (True, EvalError, "AX_ERR_NOW_UTC_MS_NOT_NUMBER"),
    (None, EvalError, "AX_ERR_NOW_UTC_MS_NOT_NUMBER"),
    (float("nan"), EvalError, "AX_ERR_NON_FINITE"),
    (float("inf"), EvalError, "AX_ERR_NON_FINITE"),
    (1700000000000.5, ArgumentError, "AX_ERR_INVALID_ARGUMENT"),
    (2 ** 53, ArgumentError, "AX_ERR_INVALID_ARGUMENT"),
    (-1, ArgumentError, "AX_ERR_INVALID_ARGUMENT"),
    (-1700000000000.0, ArgumentError, "AX_ERR_INVALID_ARGUMENT"),
)


@test("clock: now_utc_ms is an exact integer, never coerced (argument path)")
def _():
    for value, exc_type, code_name in NOW_REJECTS:
        if value is None:
            continue  # None means "absent" for the argument, not a bad value
        assert_raises(exc_type,
                      lambda v=value: engine.evaluate(BYTECODE, {"amount": 1.0},
                                                      now_utc_ms=v),
                      code_name=code_name)
    # int and integral float are the two accepted spellings of the same instant.
    assert_eq(engine.evaluate(BYTECODE, {"amount": 30000.0}, now_utc_ms=NOW).rule_name,
              engine.evaluate(BYTECODE, {"amount": 30000.0},
                              now_utc_ms=float(NOW)).rule_name)


@test("clock: the now_utc_ms FIELD path enforces the identical corpus")
def _():
    for value, exc_type, code_name in NOW_REJECTS:
        assert_raises(exc_type,
                      lambda v=value: engine.evaluate(
                          BYTECODE, {"amount": 1.0, "now_utc_ms": v}),
                      code_name=code_name)
    # And a valid field clock still works, in both spellings.
    assert_eq(engine.evaluate(BYTECODE, {"amount": 30000.0,
                                         "now_utc_ms": NOW}).rule_name,
              engine.evaluate(BYTECODE, {"amount": 30000.0,
                                         "now_utc_ms": float(NOW)}).rule_name)


@test("clock: supplying both an argument and a field is refused")
def _():
    """The argument used to overwrite the field with no diagnostic, so the
    caller's field value silently did not apply."""
    exc = assert_raises(
        ArgumentError,
        lambda: engine.evaluate(BYTECODE, {"amount": 1.0, "now_utc_ms": NOW},
                                now_utc_ms=NOW),
        code_name="AX_ERR_INVALID_ARGUMENT",
        contains=("both",))
    assert_true("overwrite" in str(exc))


@test("fidelity: a huge integer reports a typed error, not OverflowError")
def _():
    """The guard fired correctly but building its MESSAGE called
    float(value), which raises OverflowError for 10**400 - replacing the
    typed error with an untyped one at the exact moment it mattered."""
    for value in (10 ** 400, -(10 ** 400), 2 ** 1024):
        exc = assert_raises(
            ArgumentError,
            lambda v=value: engine.evaluate(BYTECODE, {"amount": v}, now_utc_ms=NOW),
            code_name="AX_ERR_INVALID_ARGUMENT")
        assert_true(len(str(exc)) < 512,
                    "message inflated to %d chars" % len(str(exc)))
    assert_raises(ArgumentError,
                  lambda: engine.evaluate(BYTECODE, {"amount": 1.0},
                                          now_utc_ms=10 ** 400),
                  code_name="AX_ERR_INVALID_ARGUMENT")


@test("fidelity: an integer too large to even print reports a typed error")
def _():
    """CPython caps int->str conversion at 4300 digits, so repr(10**5000)
    raises ValueError. Building the message for a typed error must not itself
    throw an untyped one - the guard fired correctly and the caller still got
    the wrong exception."""
    for value in (10 ** 5000, -(10 ** 5000), 2 ** 40000):
        exc = assert_raises(
            ArgumentError,
            lambda v=value: engine.evaluate(BYTECODE, {"amount": v}, now_utc_ms=NOW),
            code_name="AX_ERR_INVALID_ARGUMENT")
        assert_true("bits" in str(exc), "message should describe the size: %s" % exc)
        assert_true(len(str(exc)) < 512, len(str(exc)))
    assert_raises(ArgumentError,
                  lambda: engine.evaluate(BYTECODE, {"amount": 1.0},
                                          now_utc_ms=10 ** 5000),
                  code_name="AX_ERR_INVALID_ARGUMENT")


@test("fidelity: a 1 MiB field name cannot inflate the exception it causes")
def _():
    """The name is VALID in every case below - it is the value that is
    rejected. Only malformed names were bounded before, so a caller with a
    legitimately huge key and one bad value got a 1 MiB exception back."""
    huge = "n" * (1024 * 1024)
    cases = [
        ("unsafe integer", 2 ** 53 + 1, ArgumentError),
        ("non-finite float", float("nan"), EvalError),
        ("NUL in the value", "TR\x00KP", ArgumentError),
        ("unsupported type", [1, 2, 3], ArgumentError),
        ("lone surrogate", "TR\ud800KP", ArgumentError),
        ("huge integer", 10 ** 5000, ArgumentError),
    ]
    oversized = []
    for label, value, exc_type in cases:
        exc = assert_raises(
            exc_type,
            lambda v=value: engine.evaluate(BYTECODE, {"amount": 1.0, huge: v},
                                            now_utc_ms=NOW))
        if len(str(exc)) >= 512:
            oversized.append("%s: %d chars" % (label, len(str(exc))))
    assert_true(not oversized, "; ".join(oversized))

    # A malformed name is still bounded too (the path that already was).
    exc = assert_raises(
        ArgumentError,
        lambda: engine.evaluate(BYTECODE, {"amount": 1.0, huge + "\x00": 1},
                                now_utc_ms=NOW),
        code_name="AX_ERR_INVALID_ARGUMENT")
    assert_true(len(str(exc)) < 512, "message is %d chars" % len(str(exc)))


@test("cleanup: the engine's own error return still resets the decision")
def _():
    """ax_decision_reset covered only the extraction block, so an engine error
    return - the most common failure there is - skipped it entirely and the
    next evaluation started from a decision the engine still owned."""
    div_zero = engine.compile("rule r { when 1 / amount > 1; then allow; }")
    calls = []
    real_reset = engine._lib.ax_decision_reset

    def counting_reset(ref):
        calls.append(1)
        return real_reset(ref)

    engine._lib.ax_decision_reset = counting_reset
    try:
        assert_raises(EvalError,
                      lambda: engine.evaluate(div_zero, {"amount": 0.0},
                                              now_utc_ms=NOW),
                      code_name="AX_ERR_DIV_ZERO")
        assert_eq(len(calls), 1, "reset skipped on the engine-error path")
    finally:
        engine._lib.ax_decision_reset = real_reset
    # And a later evaluation is unaffected.
    assert_eq(engine.evaluate(BYTECODE, {"amount": 30000.0},
                              now_utc_ms=NOW).rule_name, "block_extreme")


@test("cleanup: a failed compile still releases whatever it allocated")
def _():
    calls = []
    real_free = engine._lib.ax_bytecode_free

    def counting_free(ref):
        calls.append(1)
        return real_free(ref)

    engine._lib.ax_bytecode_free = counting_free
    try:
        assert_raises(CompileError, lambda: engine.compile("this is not a rule"))
        # Either the engine allocated nothing (nothing to free) or it did and
        # the free ran; what must never happen is an allocation with no free.
        assert_true(len(calls) <= 1, calls)
        # A good compile still frees exactly once.
        before = len(calls)
        engine.compile("rule ok { when amount > 1; then allow; }")
        assert_eq(len(calls), before + 1, "successful compile did not free")
    finally:
        engine._lib.ax_bytecode_free = real_free


@test("fidelity: text with no UTF-8 form is refused, never replaced")
def _():
    """A lone surrogate is a legal str and an illegal UTF-8 sequence.
    Unrefused it escaped as a raw UnicodeEncodeError from the middle of
    _build_fields; encoding with errors='replace' would have been worse, since
    the engine would then evaluate U+FFFD while the caller believed otherwise."""
    lone = "TR\ud800KP"
    assert_raises(ArgumentError,
                  lambda: engine.evaluate(BYTECODE, {"amount": 1.0, "c": lone},
                                          now_utc_ms=NOW),
                  code_name="AX_ERR_INVALID_ARGUMENT",
                  contains=("UTF-8",))
    assert_raises(ArgumentError,
                  lambda: engine.evaluate(BYTECODE, {"amount": 1.0, lone: "x"},
                                          now_utc_ms=NOW),
                  code_name="AX_ERR_INVALID_ARGUMENT",
                  contains=("UTF-8",))
    assert_raises(ArgumentError,
                  lambda: engine.compile("rule a { when amount > 1; then allow; }"
                                         "// " + lone),
                  code_name="AX_ERR_INVALID_ARGUMENT",
                  contains=("UTF-8",))
    # The engine is untouched by the refusals.
    assert_eq(engine.evaluate(BYTECODE, {"amount": 30000.0},
                              now_utc_ms=NOW).rule_name, "block_extreme")


@test("cleanup: a failed evaluation still resets the native decision")
def _():
    """ax_decision_reset used to sit in the try block, so a decode failure
    between the native call and the reset left the decision unreleased and the
    next evaluation inheriting its state."""
    calls = []
    real_reset = engine._lib.ax_decision_reset

    def counting_reset(ref):
        calls.append(1)
        return real_reset(ref)

    engine._lib.ax_decision_reset = counting_reset
    try:
        # Force a failure inside the extraction block, after the engine call.
        real_decode = RuleDSL._decode_result
        RuleDSL._decode_result = staticmethod(
            lambda what, raw: (_ for _ in ()).throw(RuntimeError("boom")))
        try:
            engine.evaluate(BYTECODE, {"amount": 30000.0}, now_utc_ms=NOW)
            raise AssertionError("the injected failure did not propagate")
        except RuntimeError:
            pass
        finally:
            # staticmethod() again on the way back: attribute access unwraps
            # the descriptor, so a bare re-assignment would rebind it as an
            # instance method and every later call would gain a stray self.
            RuleDSL._decode_result = staticmethod(real_decode)
        assert_eq(len(calls), 1, "ax_decision_reset was not called on the error path")
    finally:
        engine._lib.ax_decision_reset = real_reset
    # The engine is still usable afterwards.
    assert_eq(engine.evaluate(BYTECODE, {"amount": 30000.0},
                              now_utc_ms=NOW).rule_name, "block_extreme")


@test("compile: a rule source containing NUL is refused")
def _():
    # A NUL ends the C string: the compiler would silently compile only the
    # prefix while a hash over the file attests to all of its bytes.
    exc = assert_raises(
        ArgumentError,
        lambda: engine.compile("rule a { when amount > 1; then allow; }\x00"
                               "rule b { when amount > 2; then decline; }"),
        code_name="AX_ERR_INVALID_ARGUMENT",
        contains=("NUL",))
    assert_true("prefix" in str(exc))
    assert_raises(ArgumentError, lambda: engine.compile(b"not a str"),
                  code_name="AX_ERR_INVALID_ARGUMENT")


# ---------------------------------------------------------------------------

print(f"\n{_passed} passed, {_failed} failed")
engine.close()
sys.exit(1 if _failed else 0)
