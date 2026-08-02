"""RuleDSL MCP input-validation tests. ENGINE-FREE: no DLL, no mcp package.

Runs first in CI, before the engine is downloaded, so the cheapest failures
surface first.

Covers ruledsl_mcp.validate (schema declaration, value safety, bounds, schema
conformance), ruledsl_mcp.errors (the five-key error object), and
ruledsl_mcp.schemas (the advertised wire schemas). Also asserts PARITY between
the two validation layers: ruledsl_mcp.validate.validate_fields and the
binding's own RuleDSL._build_fields must reject the same values. That
duplication is deliberate (see validate.py's docstring) and this is what keeps
it from drifting.

RuleDSL._build_fields is a @staticmethod, so it needs ctypes but NOT the
engine library.
"""

import ast
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

sys.path.insert(0, str(REPO_ROOT / "bindings" / "python"))
from ruledsl_mcp import errors, schemas, validate  # noqa: E402
from ruledsl_mcp.validate import (  # noqa: E402
    FieldValidationError,
    SchemaDeclarationError,
    check_schema,
    validate_fields,
    validate_now_utc_ms,
)

WRAPPER_DIR = os.environ.get(
    "RULEDSL_WRAPPER", str(REPO_ROOT / "bindings" / "python"))
sys.path.insert(0, WRAPPER_DIR)
from ruledsl import RuleDSL, RuleDSLError  # noqa: E402

# ---------------------------------------------------------------------------
# Test infrastructure (same harness style as the other tests/mcp modules)
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0


def test(name):
    def decorator(fn):
        global _passed, _failed
        try:
            fn()
            _passed += 1
            print(f"  PASS  {name}")
        except Exception as e:
            _failed += 1
            print(f"  FAIL  {name}: {e}")
        return fn
    return decorator


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(msg or "condition is false")


def assert_eq(a, b, msg=""):
    if a != b:
        raise AssertionError(f"Expected {b!r}, got {a!r}" + (f" ({msg})" if msg else ""))


def assert_rejects(fields, schema, domain, code, name, field=None):
    """Assert validate_fields rejects with the exact section-5 error."""
    try:
        validate_fields(fields, schema)
    except FieldValidationError as exc:
        err = exc.error
        assert_eq(err["error_domain"], domain, "error_domain")
        assert_eq(err["error_code"], code, "error_code")
        assert_eq(err["error_name"], name, "error_name")
        if field is not None:
            assert_eq(err["field"], field, "field")
        assert_true(set(err) == {"error_domain", "error_code", "error_name",
                                 "message", "field"},
                    f"error object keys drifted: {sorted(err)}")
        # An error must never be inflated by the input it rejects.
        assert_true(len(err["message"]) < 512,
                    f"error message is {len(err['message'])} bytes: {err['message'][:120]}")
        return err
    raise AssertionError(f"not rejected: {list(fields)[:4]}")


def assert_schema_invalid(schema, fragment=""):
    try:
        check_schema(schema, "r")
    except SchemaDeclarationError as e:
        if fragment and fragment not in str(e):
            raise AssertionError(f"message missing {fragment!r}: {e}")
        return e
    raise AssertionError("SchemaDeclarationError not raised")


AMOUNT_SCHEMA = check_schema({
    "type": "object",
    "additionalProperties": False,
    "required": ["amount"],
    "properties": {"amount": {"type": "number", "minimum": 0}},
}, "amount_only")

OPEN_SCHEMA = check_schema({
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "amount": {"type": "number"},
        "note": {"type": "string"},
        "flag": {"type": "boolean"},
        "maybe": {"type": ["string", "null"]},
    },
}, "open")


# ---------------------------------------------------------------------------
# Schema declaration
# ---------------------------------------------------------------------------

@test("schema: the shipped rules/manifest.json schemas are all accepted")
def _():
    import json
    manifest = json.loads((REPO_ROOT / "rules" / "manifest.json").read_text("utf-8"))
    rules = manifest["rules"]
    assert_true(rules, "manifest declares no rules")
    for rule_id, spec in rules.items():
        assert_true("input_schema" in spec,
                    f"rule {rule_id!r} declares no input_schema")
        check_schema(spec["input_schema"], rule_id)


@test("schema: an unknown keyword is fatal, never silently ignored")
def _():
    # The core discipline: the server must not present a constraint as enforced
    # when it is not. `pattern` is the concrete case - excluded on purpose.
    assert_schema_invalid(
        {"type": "object", "properties": {"a": {"type": "string", "pattern": "^x"}}},
        "pattern")
    assert_schema_invalid(
        {"type": "object", "properties": {}, "nullable": True}, "nullable")


@test("schema: non-scalar field types are refused at declaration")
def _():
    # object/array cannot cross the AXValue boundary, so a schema promising
    # them would promise something the engine can never accept.
    for bad in ("object", "array"):
        assert_schema_invalid(
            {"type": "object", "properties": {"a": {"type": bad}}}, "scalar")


@test("schema: the closed world is not optional")
def _():
    assert_schema_invalid(
        {"type": "object", "properties": {}, "additionalProperties": True},
        "additionalProperties")
    assert_schema_invalid(
        {"type": "object", "properties": {}, "additionalProperties": {"type": "string"}},
        "additionalProperties")


@test("schema: malformed declarations are refused")
def _():
    assert_schema_invalid("not an object")
    assert_schema_invalid({"type": "array", "properties": {}}, "object")
    assert_schema_invalid({"type": "object"}, "properties")
    assert_schema_invalid({"type": "object", "properties": {"a": {}}}, "type")
    assert_schema_invalid(
        {"type": "object", "properties": {}, "required": ["ghost"]}, "ghost")
    assert_schema_invalid(
        {"type": "object", "properties": {"a": {"type": "number", "enum": []}}}, "enum")
    assert_schema_invalid(
        {"type": "object",
         "properties": {"a": {"type": "number", "enum": ["not a number"]}}}, "enum")
    assert_schema_invalid(
        {"type": "object",
         "properties": {"a": {"type": "number", "minimum": 5, "maximum": 1}}}, "maximum")
    assert_schema_invalid(
        {"type": "object", "properties": {"a": {"type": "number", "minLength": 1}}},
        "string")
    assert_schema_invalid(
        {"type": "object", "properties": {"a": {"type": "string", "maxLength": -1}}},
        "non-negative")


# ---------------------------------------------------------------------------
# Value safety
# ---------------------------------------------------------------------------

# Values the engine cannot receive faithfully. BOTH validation layers must
# reject every one of these - see the parity test below.
HOSTILE_VALUES = [
    ("NUL in string", {"amount": 1.0, "country": "TR\x00KP"}),
    ("unsafe integer +", {"amount": 2 ** 53 + 1}),
    ("unsafe integer -", {"amount": -(2 ** 53 + 1)}),
    ("nan", {"amount": float("nan")}),
    ("inf", {"amount": float("inf")}),
    ("-inf", {"amount": float("-inf")}),
    ("nested object", {"amount": {"a": 1}}),
    ("array", {"amount": [1, 2]}),
    ("bytes", {"amount": b"x"}),
    ("NUL in field name", {"a\x00b": 1.0}),
    ("empty field name", {"": 1.0}),
    ("non-string field name", {123: 1.0}),
]


@test("value: a string containing NUL is refused, not silently truncated")
def _():
    # An audit passed {"country": "TR\x00KP"}: the record kept the whole string
    # while the engine matched a rule on "TR".
    assert_rejects({"amount": 1.0, "country": "TR\x00KP"}, None,
                   "server", errors.SRV_UNSAFE_FIELD_VALUE, "SRV_UNSAFE_FIELD_VALUE",
                   "fields.country")


@test("value: an integer beyond 2**53-1 is refused, not silently rounded")
def _():
    # 9007199254740993 was logged verbatim while the engine evaluated
    # 9007199254740992.
    for value in (2 ** 53 + 1, -(2 ** 53 + 1), 10 ** 30):
        assert_rejects({"account": value}, None, "server",
                       errors.SRV_UNSAFE_FIELD_VALUE, "SRV_UNSAFE_FIELD_VALUE",
                       "fields.account")
    # The boundary itself is exactly representable and must be accepted.
    validate_fields({"account": validate.MAX_SAFE_INTEGER}, None)
    validate_fields({"account": -validate.MAX_SAFE_INTEGER}, None)


@test("value: non-finite floats keep the engine's own AX_ERR_NON_FINITE")
def _():
    # Section 5: a failure the engine already defines is reported with the
    # engine's code, not a new server one.
    for value in (float("nan"), float("inf"), float("-inf")):
        assert_rejects({"amount": value}, None, "engine",
                       errors.AX_ERR_NON_FINITE, "AX_ERR_NON_FINITE", "fields.amount")


@test("value: non-scalar values are refused")
def _():
    from decimal import Decimal
    for value in ({"a": 1}, [1, 2], (1,), b"x", Decimal("1"), object()):
        assert_rejects({"x": value}, None, "server",
                       errors.SRV_UNSAFE_FIELD_VALUE, "SRV_UNSAFE_FIELD_VALUE",
                       "fields.x")


@test("value: malformed field names are refused")
def _():
    assert_rejects({"a\x00b": 1.0}, None, "server",
                   errors.SRV_FIELD_NAME_INVALID, "SRV_FIELD_NAME_INVALID")
    assert_rejects({"": 1.0}, None, "server",
                   errors.SRV_FIELD_NAME_INVALID, "SRV_FIELD_NAME_INVALID")
    assert_rejects({123: 1.0}, None, "server",
                   errors.SRV_FIELD_NAME_INVALID, "SRV_FIELD_NAME_INVALID")


@test("value: safe values are accepted")
def _():
    validate_fields({}, None)
    validate_fields({"a": 0, "b": -0.0, "c": True, "d": False, "e": None,
                     "f": "", "g": "x" * 4096, "h": 2 ** 53 - 1}, None)


@test("value: fields must be an object")
def _():
    for bad in ([], "x", 1, None):
        try:
            validate_fields(bad, None)
            raise AssertionError(f"not rejected: {bad!r}")
        except FieldValidationError as e:
            assert_eq(e.error["error_domain"], "engine")
            assert_eq(e.error["error_name"], "AX_ERR_INVALID_ARGUMENT")


# ---------------------------------------------------------------------------
# The bool/int trap
# ---------------------------------------------------------------------------

@test("bool: True is a boolean, never a number (isinstance(True, int) trap)")
def _():
    bool_schema = check_schema(
        {"type": "object", "properties": {"x": {"type": "boolean"}}}, "b")
    number_schema = check_schema(
        {"type": "object", "properties": {"x": {"type": "number"}}}, "n")
    integer_schema = check_schema(
        {"type": "object", "properties": {"x": {"type": "integer"}}}, "i")

    validate_fields({"x": True}, bool_schema)
    for schema in (number_schema, integer_schema):
        assert_rejects({"x": True}, schema, "server",
                       errors.SRV_SCHEMA_VIOLATION, "SRV_SCHEMA_VIOLATION", "fields.x")
    # and a number is not a boolean
    assert_rejects({"x": 1}, bool_schema, "server",
                   errors.SRV_SCHEMA_VIOLATION, "SRV_SCHEMA_VIOLATION", "fields.x")


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------

@test("bounds: field count, name size, string size, and total encoding")
def _():
    assert_rejects({f"f{i}": 1.0 for i in range(validate.MAX_FIELD_COUNT + 1)}, None,
                   "server", errors.SRV_FIELDS_TOO_LARGE, "SRV_FIELDS_TOO_LARGE",
                   "fields")
    validate_fields({f"f{i}": 1.0 for i in range(validate.MAX_FIELD_COUNT)}, None)

    assert_rejects({"n" * (validate.MAX_FIELD_NAME_BYTES + 1): 1.0}, None,
                   "server", errors.SRV_FIELDS_TOO_LARGE, "SRV_FIELDS_TOO_LARGE")
    validate_fields({"n" * validate.MAX_FIELD_NAME_BYTES: 1.0}, None)

    assert_rejects({"s": "x" * (validate.MAX_STRING_BYTES + 1)}, None,
                   "server", errors.SRV_FIELDS_TOO_LARGE, "SRV_FIELDS_TOO_LARGE",
                   "fields.s")

    # Under every per-value cap, over the total. 32 fields x ~4 KiB > 64 KiB.
    big = {f"f{i}": "x" * (validate.MAX_STRING_BYTES - 1) for i in range(32)}
    assert_rejects(big, None, "server", errors.SRV_FIELDS_TOO_LARGE,
                   "SRV_FIELDS_TOO_LARGE", "fields")


@test("bounds: a 1 MiB field is refused and does not inflate the error")
def _():
    # An audit sent a 1 MiB unused field and got a ~1.049 MiB response and a
    # ~1.049 MiB log line back.
    err = assert_rejects({"amount": 1.0, "big": "x" * (1024 * 1024)}, None,
                         "server", errors.SRV_FIELDS_TOO_LARGE, "SRV_FIELDS_TOO_LARGE",
                         "fields.big")
    assert_true(len(errors.canonical_json(err)) < 1024,
                "the error response scales with the rejected input")


# ---------------------------------------------------------------------------
# Schema conformance
# ---------------------------------------------------------------------------

@test("conformance: a numeric string is refused where a number is declared")
def _():
    # THE headline regression. Shipped v0.9 makes cross-type comparisons return
    # false with no error and does no static type checking
    # (docs/language/conformance_status_v0_9.md, SEM-0018 and TYP-0003/0004),
    # so "2000" silently fell through every threshold and reached the fallback
    # rule - a fail-open. It is now a hard rejection naming the field.
    err = assert_rejects({"amount": "2000"}, AMOUNT_SCHEMA, "server",
                         errors.SRV_SCHEMA_VIOLATION, "SRV_SCHEMA_VIOLATION",
                         "fields.amount")
    assert_true("string" in err["message"], err["message"])
    validate_fields({"amount": 2000.0}, AMOUNT_SCHEMA)
    validate_fields({"amount": 2000}, AMOUNT_SCHEMA)


@test("conformance: undeclared and missing fields are refused")
def _():
    assert_rejects({"amount": 1.0, "ghost": 1.0}, AMOUNT_SCHEMA, "server",
                   errors.SRV_SCHEMA_VIOLATION, "SRV_SCHEMA_VIOLATION", "fields.ghost")
    assert_rejects({}, AMOUNT_SCHEMA, "server",
                   errors.SRV_SCHEMA_VIOLATION, "SRV_SCHEMA_VIOLATION", "fields.amount")


@test("conformance: integer accepts an integral float, rejects a fractional one")
def _():
    schema = check_schema(
        {"type": "object", "properties": {"n": {"type": "integer"}}}, "i")
    validate_fields({"n": 2000}, schema)
    validate_fields({"n": 2000.0}, schema)  # JSON draws no int/float distinction
    assert_rejects({"n": 2000.5}, schema, "server",
                   errors.SRV_SCHEMA_VIOLATION, "SRV_SCHEMA_VIOLATION", "fields.n")


@test("conformance: enum, minimum, maximum, minLength, maxLength")
def _():
    schema = check_schema({
        "type": "object",
        "properties": {
            "code": {"type": "string", "enum": ["TR", "DE"], "minLength": 2,
                     "maxLength": 2},
            "score": {"type": "number", "minimum": 0, "maximum": 100},
        },
    }, "constrained")
    validate_fields({"code": "TR", "score": 50}, schema)
    for fields in ({"code": "US"}, {"score": -1}, {"score": 101}):
        assert_rejects(fields, schema, "server", errors.SRV_SCHEMA_VIOLATION,
                       "SRV_SCHEMA_VIOLATION")

    lengths = check_schema({
        "type": "object",
        "properties": {"s": {"type": "string", "minLength": 2, "maxLength": 4}},
    }, "lengths")
    validate_fields({"s": "abc"}, lengths)
    for value in ("a", "abcde"):
        assert_rejects({"s": value}, lengths, "server", errors.SRV_SCHEMA_VIOLATION,
                       "SRV_SCHEMA_VIOLATION", "fields.s")


@test("conformance: a union type with bounds does not raise on a string")
def _():
    # ["number", "string"] carrying a minimum: comparing a str against it would
    # be a TypeError rather than a reported violation.
    schema = check_schema({
        "type": "object",
        "properties": {"v": {"type": ["number", "string"], "minimum": 10}},
    }, "union")
    validate_fields({"v": "anything"}, schema)
    validate_fields({"v": 11}, schema)
    assert_rejects({"v": 9}, schema, "server", errors.SRV_SCHEMA_VIOLATION,
                   "SRV_SCHEMA_VIOLATION", "fields.v")


@test("determinism: the reported error does not depend on key insertion order")
def _():
    # Two clients sending the same object must get the same error, whatever
    # order their JSON serializer produced.
    forward = {"zeta": "TR\x00KP", "alpha": 2 ** 53 + 1}
    reverse = {"alpha": 2 ** 53 + 1, "zeta": "TR\x00KP"}
    first = assert_rejects(forward, None, "server", errors.SRV_UNSAFE_FIELD_VALUE,
                           "SRV_UNSAFE_FIELD_VALUE")
    second = assert_rejects(reverse, None, "server", errors.SRV_UNSAFE_FIELD_VALUE,
                            "SRV_UNSAFE_FIELD_VALUE")
    assert_eq(first, second, "error depends on key order")
    assert_eq(first["field"], "fields.alpha", "sorted iteration reports the first key")


# ---------------------------------------------------------------------------
# The clock
# ---------------------------------------------------------------------------

@test("clock: now_utc_ms must be an exact integer in the safe range")
def _():
    def rejects(value, domain, code, name):
        try:
            validate_now_utc_ms(value)
        except FieldValidationError as e:
            assert_eq(e.error["error_domain"], domain)
            assert_eq(e.error["error_code"], code)
            assert_eq(e.error["error_name"], name)
            assert_eq(e.error["field"], "now_utc_ms")
            return
        raise AssertionError(f"not rejected: {value!r}")

    validate_now_utc_ms(1700000000000)
    validate_now_utc_ms(1700000000000.0)
    validate_now_utc_ms(0)

    # Absence and non-numeric types are the engine's own conditions...
    rejects(None, "engine", errors.AX_ERR_MISSING_NOW_UTC_MS, "AX_ERR_MISSING_NOW_UTC_MS")
    rejects("1700000000000", "engine", errors.AX_ERR_NOW_UTC_MS_NOT_NUMBER,
            "AX_ERR_NOW_UTC_MS_NOT_NUMBER")
    rejects(True, "engine", errors.AX_ERR_NOW_UTC_MS_NOT_NUMBER,
            "AX_ERR_NOW_UTC_MS_NOT_NUMBER")
    rejects(float("nan"), "engine", errors.AX_ERR_NON_FINITE, "AX_ERR_NON_FINITE")
    # ...while "numeric but not a whole millisecond" is one the engine cannot see.
    rejects(1700000000000.5, "server", errors.SRV_NOW_UTC_MS_NOT_INTEGER,
            "SRV_NOW_UTC_MS_NOT_INTEGER")
    rejects(2 ** 53, "server", errors.SRV_NOW_UTC_MS_NOT_INTEGER,
            "SRV_NOW_UTC_MS_NOT_INTEGER")
    # The advertised schema says minimum: 0. Accepting -1 would honour a
    # contract the server does not advertise.
    rejects(-1, "server", errors.SRV_NOW_UTC_MS_NOT_INTEGER,
            "SRV_NOW_UTC_MS_NOT_INTEGER")
    rejects(-1.0, "server", errors.SRV_NOW_UTC_MS_NOT_INTEGER,
            "SRV_NOW_UTC_MS_NOT_INTEGER")


@test("clock: an integral float normalizes to the identical int")
def _():
    """1700000000000 and 1700000000000.0 are the same instant, so they must
    produce the same canonical record - not `...000` versus `...000.0`."""
    from_int = validate_now_utc_ms(1700000000000)
    from_float = validate_now_utc_ms(1700000000000.0)
    assert_eq(type(from_int), int)
    assert_eq(type(from_float), int)
    assert_eq(from_int, from_float)
    assert_eq(errors.canonical_json({"now_utc_ms": from_int}),
              errors.canonical_json({"now_utc_ms": from_float}))
    assert_eq(errors.canonical_json({"now_utc_ms": from_float}),
              '{"now_utc_ms":1700000000000}')
    assert_eq(validate_now_utc_ms(0), 0)


@test("schema declaration: a non-finite bound is refused")
def _():
    """NaN passes isinstance(x, float) and every comparison against it is
    False, so a NaN bound is a constraint that silently never fires."""
    for bad in (float("nan"), float("inf"), float("-inf")):
        for key in ("minimum", "maximum"):
            try:
                check_schema({"type": "object", "properties": {
                    "a": {"type": "number", key: bad}}}, "r")
            except SchemaDeclarationError:
                continue
            raise AssertionError("accepted %s: %r" % (key, bad))


@test("enum: membership is by JSON type, so True never matches 1")
def _():
    """Python says True == 1, so a bare `in` would let a boolean satisfy an
    enum that only lists the number 1."""
    def schema(spec):
        return check_schema(
            {"type": "object", "properties": {"a": spec}}, "r")

    number_enum = schema({"type": "number", "enum": [1]})
    validate_fields({"a": 1}, number_enum)      # int 1
    validate_fields({"a": 1.0}, number_enum)    # 1.0 is the same JSON number
    assert_rejects({"a": True}, number_enum, "server",
                   errors.SRV_SCHEMA_VIOLATION, "SRV_SCHEMA_VIOLATION")

    bool_enum = schema({"type": ["boolean", "integer"], "enum": [True]})
    validate_fields({"a": True}, bool_enum)
    assert_rejects({"a": 1}, bool_enum, "server",
                   errors.SRV_SCHEMA_VIOLATION, "SRV_SCHEMA_VIOLATION")

    # The union type is what makes this reachable: with type "number" alone the
    # type check would already refuse a bool, hiding the enum defect.
    union_enum = schema({"type": ["boolean", "integer"], "enum": [1]})
    validate_fields({"a": 1}, union_enum)
    assert_rejects({"a": True}, union_enum, "server",
                   errors.SRV_SCHEMA_VIOLATION, "SRV_SCHEMA_VIOLATION")


@test("output schema: check_output accepts a conforming payload and no other")
def _():
    """The SDK validates a success against a model derived from the return
    annotation, not against the schema attached to the tool, so this checker is
    what makes the advertised outputSchema mean anything."""
    good = {
        "rules": [{"rule_id": "r", "version": "1.0.0", "rule_sha256": "a" * 64,
                   "input_schema": {"type": "object"}}],
    }
    schemas.check_output("list_rules", good)

    def rejects(payload, fragment):
        try:
            schemas.check_output("list_rules", payload)
        except schemas.OutputSchemaViolation as exc:
            assert_true(fragment in str(exc), f"{fragment!r} not in {exc}")
            return
        raise AssertionError("accepted: %r" % (payload,))

    import copy
    missing = copy.deepcopy(good)
    del missing["rules"][0]["rule_sha256"]
    rejects(missing, "missing required")

    extra = copy.deepcopy(good)
    extra["rules"][0]["surprise"] = 1
    rejects(extra, "undeclared key")

    bad_type = copy.deepcopy(good)
    bad_type["rules"][0]["version"] = 1
    rejects(bad_type, "expected string")

    bad_pattern = copy.deepcopy(good)
    bad_pattern["rules"][0]["rule_sha256"] = "not-a-sha"
    rejects(bad_pattern, "does not match")

    # bool is not an integer here either.
    try:
        schemas.check_output("engine_info", {
            "engine_version": "1.0.2", "abi_level": True,
            "bytecode_schema_version": 1, "decision_record_schema": "s",
            "server_version": "0.2.0", "manifest_sha256": "b" * 64})
    except schemas.OutputSchemaViolation:
        pass
    else:
        raise AssertionError("a boolean satisfied an integer/null field")


@test("errors: the object is bounded by serialized bytes, not characters")
def _():
    """A character cap cannot see JSON escaping: ensure_ascii turns one emoji
    into twelve characters, and the object travels twice in one response."""
    backslash = chr(92)
    corpus = {
        "ascii": ("x" * 4000, "fields." + "y" * 4000),
        "unicode": ("uüç" * 2000, "fields." + "\U0001f600" * 1000),
        "control": ("\x01\x02" * 2000, "fields." + "\x07" * 2000),
        "backslash": ((backslash + '"') * 2000, "fields." + backslash * 2000),
    }
    for name, (message, field) in sorted(corpus.items()):
        err = errors.server_error(errors.SRV_UNKNOWN_ARGUMENT, message, field)
        size = len(errors.canonical_json(err).encode("utf-8"))
        assert size <= errors.MAX_ERROR_JSON_BYTES, (name, size)
        # What a client branches on always survives truncation.
        assert_eq(err["error_domain"], "server")
        assert_eq(err["error_code"], errors.SRV_UNKNOWN_ARGUMENT)
        assert_eq(err["error_name"], "SRV_UNKNOWN_ARGUMENT")
        # Deterministic: the same oversized input yields the same error.
        assert_eq(err, errors.server_error(
            errors.SRV_UNKNOWN_ARGUMENT, message, field))

    # A message that already fits is left completely alone.
    small = errors.server_error(errors.SRV_RESERVED_FIELD, "short", "fields.a")
    assert_eq(small["message"], "short")
    assert_eq(small["field"], "fields.a")


# ---------------------------------------------------------------------------
# Parity with the binding's own value safety
# ---------------------------------------------------------------------------

@test("parity: validate.py and ruledsl.py reject the same hostile values")
def _():
    # validate.py deliberately does not import ruledsl (that would drag ctypes
    # into this 3.10+ package and couple it to the 3.7-compatible binding), so
    # a few predicates are duplicated. This is the anti-drift device for that
    # duplication: one table, both layers.
    for label, fields in HOSTILE_VALUES:
        try:
            validate_fields(fields, None)
            raise AssertionError(f"validate.py accepted {label}")
        except FieldValidationError:
            pass
        try:
            RuleDSL._build_fields(fields)
            raise AssertionError(f"ruledsl.py accepted {label}")
        except RuleDSLError:
            pass


@test("parity: both layers accept the same safe boundary values")
def _():
    safe = {"a": 0, "b": -0.0, "c": True, "d": None, "e": "",
            "f": 2 ** 53 - 1, "g": -(2 ** 53 - 1)}
    validate_fields(safe, None)
    RuleDSL._build_fields(safe)


# ---------------------------------------------------------------------------
# Advertised wire schemas
# ---------------------------------------------------------------------------

@test("schemas: the three tools each declare an input and an output schema")
def _():
    assert_eq(sorted(schemas.TOOL_SCHEMAS), ["engine_info", "evaluate_case", "list_rules"])
    for name, (input_schema, output_schema) in schemas.TOOL_SCHEMAS.items():
        assert_eq(input_schema["type"], "object", name)
        assert_eq(output_schema["type"], "object", name)
        assert_true(output_schema["properties"], f"{name} advertises no output shape")


@test("schemas: now_utc_ms is advertised as an integer")
def _():
    # docs/design/mcp_server_v0.md said integer from the start while the
    # implementation used float, which is what let a numeric string through.
    now = schemas.EVALUATE_CASE_INPUT["properties"]["now_utc_ms"]
    assert_eq(now["type"], "integer")
    assert_eq(now["maximum"], validate.MAX_SAFE_INTEGER)


@test("schemas: fields advertises scalar-only values and a closed argument set")
def _():
    fields = schemas.EVALUATE_CASE_INPUT["properties"]["fields"]
    assert_eq(sorted(fields["additionalProperties"]["type"]),
              ["boolean", "null", "number", "string"])
    assert_eq(schemas.EVALUATE_CASE_INPUT["additionalProperties"], False)
    assert_eq(sorted(schemas.EVALUATE_CASE_INPUT["required"]),
              ["fields", "now_utc_ms", "rule_id"])


@test("schemas: list_rules advertises input_schema so a caller can comply")
def _():
    item = schemas.LIST_RULES_OUTPUT["properties"]["rules"]["items"]
    assert_true("input_schema" in item["required"],
                "discovery does not carry the per-rule contract")


@test("errors: server codes are a contiguous, uniquely named, append-only set")
def _():
    names = errors.SERVER_ERROR_NAMES
    assert_eq(sorted(names), list(range(1, 10)), "server codes 1-9")
    assert_eq(len(set(names.values())), len(names), "duplicate error name")
    # The two codes that shipped in v0 must keep their meaning forever.
    assert_eq(names[1], "SRV_UNKNOWN_RULE_ID")
    assert_eq(names[2], "SRV_RESERVED_FIELD")


@test("errors: the error object always carries all five keys")
def _():
    for err in (errors.server_error(errors.SRV_INTERNAL, "x"),
                errors.server_error(errors.SRV_SCHEMA_VIOLATION, "x", "fields.a"),
                errors.engine_error(errors.AX_ERR_NON_FINITE, "x")):
        assert_eq(sorted(err),
                  ["error_code", "error_domain", "error_name", "field", "message"])
    assert_eq(errors.server_error(errors.SRV_INTERNAL, "x")["field"], None,
              "unscoped errors carry an explicit null field")


@test("errors: an interpolated value can never inflate a message")
def _():
    assert_true(len(errors.summarize("x" * 100000)) < 128)
    assert_true(len(errors.summarize(list(range(10000)))) < 128)


# ---------------------------------------------------------------------------
# Source-level invariants
# ---------------------------------------------------------------------------

@test("source: ruledsl_mcp contains no bare assert (python -O strips them)")
def _():
    # A correctness check written as `assert` disappears under `python -O`, in
    # exactly the configuration most likely to be running in production. The
    # decision-record shape check used to be one; it is now part of the error
    # contract. This scan keeps another from creeping in.
    package = REPO_ROOT / "bindings" / "python" / "ruledsl_mcp"
    offenders = []
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                offenders.append(f"{path.name}:{node.lineno}")
    assert_eq(offenders, [], "bare assert in shipped server code")


@test("source: ruledsl_mcp has no from-imports of ruledsl (engine-free by contract)")
def _():
    # library.py, handlers.py and validate.py must stay importable with no
    # engine present; server.py imports the binding inside main(), not at
    # module scope, for the same reason.
    package = REPO_ROOT / "bindings" / "python" / "ruledsl_mcp"
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert_true(alias.name.split(".")[0] != "ruledsl"
                                or _inside_function(tree, node),
                                f"{path.name} imports ruledsl at module scope")


def _inside_function(tree, target):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target:
                    return True
    return False


# ---------------------------------------------------------------------------

print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
