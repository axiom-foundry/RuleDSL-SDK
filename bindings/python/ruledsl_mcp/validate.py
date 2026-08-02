"""Fail-closed validation of MCP call inputs. Pure stdlib, engine-free.

Design contract: docs/design/mcp_server_v0.md sections 5, 6 and 9.

Two jobs, in this order:

  1. Value safety - refuse anything the engine cannot receive faithfully, so
     the decision log can never attest to a value the engine did not see.
  2. Schema conformance - check `fields` against the rule's manifest-declared
     input_schema (manifest v2).

Both run BEFORE the engine is called and before anything is logged, so a
rejected call writes no decision record.

Why this duplicates a few predicates from bindings/python/ruledsl.py: that
module is the backstop for every binding user, including non-MCP embedders,
and it raises exceptions. This module is the MCP contract: it produces the
stable {error_domain, error_code, error_name, message, field} object, enforces
byte and count bounds the binding has no business imposing on embedders, and
knows about input_schema, which the binding does not. Importing ruledsl here
would drag ctypes in and couple this 3.10+ package to the 3.7-compatible
binding. tests/mcp/test_validate.py asserts both layers reject the same values,
which is the anti-drift device for the duplication.
"""

import math

from . import errors

# Declared bounds (design doc section 9). These are contract, not heuristics:
# a caller can rely on anything within them being accepted.
MAX_FIELD_COUNT = 64
MAX_FIELD_NAME_BYTES = 128
MAX_STRING_BYTES = 4096          # aligned with the engine's own LIMIT_STRING
MAX_FIELDS_JSON_BYTES = 65536

# Largest integer that survives a round trip through IEEE 754 binary64, the
# only numeric type the engine has.
MAX_SAFE_INTEGER = 2 ** 53 - 1

SCALAR_TYPES = ("number", "integer", "string", "boolean", "null")

_ROOT_KEYS = frozenset(
    ("type", "properties", "required", "additionalProperties", "description"))
_FIELD_KEYS = frozenset(
    ("type", "enum", "minimum", "maximum", "minLength", "maxLength", "description"))


class SchemaDeclarationError(Exception):
    """A manifest-declared input_schema is itself malformed.

    Raised at library load time, so a rule whose schema cannot be understood is
    never served. The server must never silently ignore a constraint someone
    believed was enforced.
    """


class FieldValidationError(Exception):
    """A call's fields are rejected. Carries the section-5 error object."""

    def __init__(self, err):
        self.error = err
        super().__init__(err["message"])


def _reject(code, message, field=None):
    raise FieldValidationError(errors.server_error(code, message, field))


def _reject_engine(code, message, field=None):
    raise FieldValidationError(errors.engine_error(code, message, field))


# ---------------------------------------------------------------------------
# Schema declaration (load time)
# ---------------------------------------------------------------------------

def check_schema(schema, rule_id):
    """Validate a manifest-declared input_schema; return it normalized.

    Supports a deliberately small JSON Schema subset (design doc section 6).
    An UNKNOWN KEYWORD IS FATAL: silently ignoring a keyword would present a
    constraint as enforced when it is not.

    `pattern` is deliberately absent. Python `re` is not ECMA-262, so the same
    hashed manifest would mean different things under a future non-Python
    server; and a manifest-supplied regex on a fail-closed path is a ReDoS
    vector with no timeout available in stdlib `re`. Because unknown keywords
    are fatal, it can be added later with no silent-ignore window.
    """
    where = "rule %r input_schema" % rule_id
    if not isinstance(schema, dict):
        raise SchemaDeclarationError(
            "%s must be an object, got %s" % (where, type(schema).__name__))

    unknown = sorted(set(schema) - _ROOT_KEYS)
    if unknown:
        raise SchemaDeclarationError(
            "%s has unsupported keyword(s) %s; supported: %s"
            % (where, unknown, sorted(_ROOT_KEYS)))

    if schema.get("type") != "object":
        raise SchemaDeclarationError(
            "%s must declare \"type\": \"object\", got %r" % (where, schema.get("type")))

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise SchemaDeclarationError("%s must declare an object 'properties'" % where)

    additional = schema.get("additionalProperties", False)
    if additional is not False:
        raise SchemaDeclarationError(
            "%s: additionalProperties must be false or absent (the closed world "
            "IS the contract), got %r" % (where, additional))

    required = schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(r, str) for r in required):
        raise SchemaDeclarationError("%s: 'required' must be an array of strings" % where)
    for name in required:
        if name not in properties:
            raise SchemaDeclarationError(
                "%s: 'required' names %r, which is not in 'properties'" % (where, name))

    normalized = {}
    for name, spec in properties.items():
        normalized[name] = _check_field_schema(spec, "%s.%s" % (where, name))

    return {"type": "object", "properties": normalized,
            "required": list(required), "additionalProperties": False}


def _check_field_schema(spec, where):
    if not isinstance(spec, dict):
        raise SchemaDeclarationError(
            "%s must be an object, got %s" % (where, type(spec).__name__))

    unknown = sorted(set(spec) - _FIELD_KEYS)
    if unknown:
        raise SchemaDeclarationError(
            "%s has unsupported keyword(s) %s; supported: %s"
            % (where, unknown, sorted(_FIELD_KEYS)))

    if "type" not in spec:
        raise SchemaDeclarationError("%s must declare a 'type'" % where)
    declared = spec["type"]
    types = declared if isinstance(declared, list) else [declared]
    if not types:
        raise SchemaDeclarationError("%s: 'type' must not be empty" % where)
    for t in types:
        if t not in SCALAR_TYPES:
            # "object"/"array" cannot cross the AXValue boundary
            # (include/axiom/ruledsl_c.h), so a schema declaring them would
            # promise something the engine can never accept.
            raise SchemaDeclarationError(
                "%s: type %r is not a scalar the engine can receive; supported: %s"
                % (where, t, list(SCALAR_TYPES)))
    types = list(types)

    numeric = bool({"number", "integer"} & set(types))
    stringy = "string" in types

    for key in ("minimum", "maximum"):
        if key in spec:
            if not numeric:
                raise SchemaDeclarationError(
                    "%s: %r applies to number/integer only" % (where, key))
            if isinstance(spec[key], bool) or not isinstance(spec[key], (int, float)):
                raise SchemaDeclarationError("%s: %r must be a number" % (where, key))
            # NaN passes isinstance(x, float), and every comparison against it
            # is False - so a NaN bound is a constraint that silently never
            # fires. Refusing a constraint we cannot understand is the whole
            # point of validating the declaration.
            if not math.isfinite(spec[key]):
                raise SchemaDeclarationError(
                    "%s: %r must be finite, got %r" % (where, key, spec[key]))
    if "minimum" in spec and "maximum" in spec and spec["minimum"] > spec["maximum"]:
        raise SchemaDeclarationError("%s: minimum is greater than maximum" % where)

    for key in ("minLength", "maxLength"):
        if key in spec:
            if not stringy:
                raise SchemaDeclarationError("%s: %r applies to string only" % (where, key))
            if isinstance(spec[key], bool) or not isinstance(spec[key], int) or spec[key] < 0:
                raise SchemaDeclarationError(
                    "%s: %r must be a non-negative integer" % (where, key))
    if ("minLength" in spec and "maxLength" in spec
            and spec["minLength"] > spec["maxLength"]):
        raise SchemaDeclarationError("%s: minLength is greater than maxLength" % where)

    if "enum" in spec:
        enum = spec["enum"]
        if not isinstance(enum, list) or not enum:
            raise SchemaDeclarationError("%s: 'enum' must be a non-empty array" % where)
        for value in enum:
            if not _type_matches(_json_type(value), types):
                raise SchemaDeclarationError(
                    "%s: enum entry %r is not one of the declared types %s"
                    % (where, value, types))
            # An entry no call can ever equal is a constraint that silently
            # never matches - NaN != NaN, and a lone surrogate cannot arrive
            # over a UTF-8 transport at all.
            if isinstance(value, float) and not math.isfinite(value):
                raise SchemaDeclarationError(
                    "%s: enum entry %r is not finite; no value can equal it"
                    % (where, value))
            if isinstance(value, str):
                try:
                    value.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise SchemaDeclarationError(
                        "%s: enum entry is not encodable as UTF-8 (%s); no call "
                        "could ever supply it" % (where, exc.reason))

    normalized = dict(spec)
    normalized["type"] = types
    return normalized


def _type_matches(actual, types):
    """Does a JSON type satisfy a declared type list?

    "integer" also satisfies "number": JSON has one number type, so a schema
    declaring "number" must accept the literal 1. Declaration checking and
    call-time checking both go through here - when only the latter widened,
    the perfectly legal {"type": "number", "enum": [1]} was refused at load.
    """
    return actual in types or (actual == "integer" and "number" in types)


def _enum_contains(enum, value):
    """Membership by (json_type, value), so booleans never match numbers."""
    key = (_json_type(value), value)
    return any(key == (_json_type(entry), entry) for entry in enum)


def _json_type(value):
    """The JSON type name of a Python value, bool checked before int."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "integer" if value.is_integer() else "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


# ---------------------------------------------------------------------------
# Call-time validation
# ---------------------------------------------------------------------------

def validate_now_utc_ms(value):
    """Check the explicit clock and return it NORMALIZED to an int.

    Absence and non-numeric types are the engine's own conditions and keep the
    engine's codes; "numeric but not a whole millisecond" is a condition the
    engine cannot see, so it gets a server code.

    The return value matters: 1700000000000 and 1700000000000.0 are the same
    instant, and mcp_decision_record_v1 promises now_utc_ms is always a JSON
    integer. Normalizing here is what makes the two calls produce a
    byte-identical canonical record instead of `...000` versus `...000.0`.

    Raises:
        FieldValidationError: carrying the section-5 error object.
    """
    if value is None:
        _reject_engine(errors.AX_ERR_MISSING_NOW_UTC_MS,
                       "now_utc_ms is required and explicit; the server never reads "
                       "a clock (design doc section 3)", "now_utc_ms")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _reject_engine(errors.AX_ERR_NOW_UTC_MS_NOT_NUMBER,
                       "now_utc_ms must be a number, got %s" % type(value).__name__,
                       "now_utc_ms")
    if isinstance(value, float):
        if not math.isfinite(value):
            _reject_engine(errors.AX_ERR_NON_FINITE,
                           "now_utc_ms must be finite, got %s" % value, "now_utc_ms")
        if not value.is_integer():
            _reject(errors.SRV_NOW_UTC_MS_NOT_INTEGER,
                    "now_utc_ms is epoch milliseconds and must be a whole number, "
                    "got %s" % errors.summarize(value), "now_utc_ms")
    if value > MAX_SAFE_INTEGER:
        _reject(errors.SRV_NOW_UTC_MS_NOT_INTEGER,
                "now_utc_ms %s is outside the exactly representable range "
                "(value > 2**53-1)" % errors.summarize(value), "now_utc_ms")
    # The advertised schema declares minimum: 0 (schemas.NOW_UTC_MS_SCHEMA).
    # Accepting a negative value would make the server honour a contract it
    # does not advertise, which is the same defect as advertising one it does
    # not honour - and a pre-1970 decision timestamp is meaningless here.
    if value < 0:
        _reject(errors.SRV_NOW_UTC_MS_NOT_INTEGER,
                "now_utc_ms %s is negative; the advertised schema declares "
                "minimum 0 (epoch milliseconds)" % errors.summarize(value),
                "now_utc_ms")
    return int(value)


def validate_fields(fields, schema):
    """Check a call's fields for value safety, then schema conformance.

    Raises FieldValidationError on the FIRST violation. Field iteration is
    sorted, so the reported error does not depend on JSON key order - two
    clients sending the same object always get the same error.
    """
    if not isinstance(fields, dict):
        _reject_engine(errors.AX_ERR_INVALID_ARGUMENT,
                       "fields must be an object, got %s" % type(fields).__name__,
                       "fields")

    if len(fields) > MAX_FIELD_COUNT:
        _reject(errors.SRV_FIELDS_TOO_LARGE,
                "too many fields: %d (limit %d)" % (len(fields), MAX_FIELD_COUNT),
                "fields")

    for name in sorted(fields, key=_sort_key):
        _check_name(name)
        _check_value(name, fields[name])

    # Safe to serialize only now: the per-value checks above already bound the
    # input at roughly 64 * (128 + 4096) bytes, so an oversized field can never
    # reach the serializer.
    encoded = len(errors.canonical_json(fields).encode("utf-8"))
    if encoded > MAX_FIELDS_JSON_BYTES:
        _reject(errors.SRV_FIELDS_TOO_LARGE,
                "fields encode to %d bytes (limit %d)" % (encoded, MAX_FIELDS_JSON_BYTES),
                "fields")

    if schema is not None:
        _check_conformance(fields, schema)


def _sort_key(name):
    """Sort keys deterministically even if a key is not a string (which is
    itself rejected, but the sort must not raise before we get there)."""
    return (0, name) if isinstance(name, str) else (1, repr(name))


def _utf8_len(text, code, what, path):
    """UTF-8 byte length, refusing text that has no UTF-8 form at all.

    A lone surrogate is a legal Python str and an illegal UTF-8 sequence.
    Unrefused it would reach canonical_json, which with ensure_ascii=True
    happily writes it back out as \\udXXX - so the decision log would record a
    value the engine could never have received.
    """
    try:
        return len(text.encode("utf-8"))
    except UnicodeEncodeError as exc:
        _reject(code, "%s is not encodable as UTF-8 (%s); the engine receives "
                      "UTF-8 bytes" % (what, exc.reason), path)


def _check_name(name):
    if not isinstance(name, str) or not name:
        _reject(errors.SRV_FIELD_NAME_INVALID,
                "field names must be non-empty strings, got %s" % errors.summarize(name),
                "fields")
    if "\x00" in name:
        # The prefix is caller-supplied and unbounded; errors.error() clips it
        # anyway, cutting here just keeps the path readable rather than a
        # half-truncated wall of text.
        _reject(errors.SRV_FIELD_NAME_INVALID,
                "field name contains a NUL character; the engine receives a "
                "NUL-terminated C string and would see only the prefix",
                "fields.%s" % name.split("\x00")[0][:32])
    encoded = _utf8_len(name, errors.SRV_FIELD_NAME_INVALID, "field name",
                        "fields.%s" % name[:32])
    if encoded > MAX_FIELD_NAME_BYTES:
        _reject(errors.SRV_FIELDS_TOO_LARGE,
                "field name is %d bytes (limit %d)" % (encoded, MAX_FIELD_NAME_BYTES),
                "fields.%s" % name[:32])


def _check_value(name, value):
    """Refuse values the engine cannot receive faithfully.

    A partially transmitted value is worse than a rejected one: the decision
    log would record what the caller sent while the engine decided on something
    else. bool is checked before int on purpose - isinstance(True, int) is the
    single most likely silent bug in this module.
    """
    path = "fields.%s" % name
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if value > MAX_SAFE_INTEGER or value < -MAX_SAFE_INTEGER:
            _reject(errors.SRV_UNSAFE_FIELD_VALUE,
                    "integer is not exactly representable as float64 "
                    "(|value| > 2**53-1); the engine would evaluate a different "
                    "number. Pass identifiers as strings.", path)
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _reject_engine(errors.AX_ERR_NON_FINITE,
                           "value is not a finite number", path)
        return
    if isinstance(value, str):
        if "\x00" in value:
            _reject(errors.SRV_UNSAFE_FIELD_VALUE,
                    "string contains a NUL character; the engine receives a "
                    "NUL-terminated C string and would see only the prefix", path)
        encoded = _utf8_len(value, errors.SRV_UNSAFE_FIELD_VALUE,
                            "string value", path)
        if encoded > MAX_STRING_BYTES:
            _reject(errors.SRV_FIELDS_TOO_LARGE,
                    "string value is %d bytes (limit %d)" % (encoded, MAX_STRING_BYTES),
                    path)
        return
    _reject(errors.SRV_UNSAFE_FIELD_VALUE,
            "unsupported value type %s; fields must be scalar (number, string, "
            "boolean, or null)" % type(value).__name__, path)


def _check_conformance(fields, schema):
    """Check fields against the rule's declared input_schema."""
    properties = schema["properties"]

    for name in sorted(fields):
        if name not in properties:
            _reject(errors.SRV_SCHEMA_VIOLATION,
                    "field is not declared by this rule's input_schema; declared: %s"
                    % sorted(properties), "fields.%s" % name)

    for name in sorted(schema["required"]):
        if name not in fields:
            _reject(errors.SRV_SCHEMA_VIOLATION,
                    "required field is missing", "fields.%s" % name)

    for name in sorted(fields):
        _check_against(name, fields[name], properties[name])


def _check_against(name, value, spec):
    path = "fields.%s" % name
    types = spec["type"]
    actual = _json_type(value)

    # "integer" accepts an int and an integral float, because JSON draws no
    # int/float distinction on the wire; "number" accepts either but NOT a
    # bool. _json_type already reports an integral float as "integer".
    if not _type_matches(actual, types):
        _reject(errors.SRV_SCHEMA_VIOLATION,
                "violates 'type': expected %s, got %s"
                % ("/".join(types), actual), path)

    # Compared as (json_type, value) pairs, never with a bare `in`. Python's ==
    # says True == 1, so `True in [1]` is True: a field declaring
    # type ["boolean","integer"] with enum [1] would accept a boolean the enum
    # never listed. Pairing also keeps 1 and 1.0 equivalent, which is correct -
    # JSON has one number type, and _json_type reports an integral float as
    # "integer".
    if "enum" in spec and not _enum_contains(spec["enum"], value):
        _reject(errors.SRV_SCHEMA_VIOLATION,
                "violates 'enum': %s is not one of %s"
                % (errors.summarize(value), errors.summarize(spec["enum"])), path)

    # Bounds apply only to an actual number. A union type such as
    # ["number", "string"] may carry a minimum, and comparing a str against it
    # would raise TypeError rather than report a violation.
    numeric_value = isinstance(value, (int, float)) and not isinstance(value, bool)
    if numeric_value:
        if "minimum" in spec and value < spec["minimum"]:
            _reject(errors.SRV_SCHEMA_VIOLATION,
                    "violates 'minimum': %s < %s"
                    % (errors.summarize(value), spec["minimum"]), path)
        if "maximum" in spec and value > spec["maximum"]:
            _reject(errors.SRV_SCHEMA_VIOLATION,
                    "violates 'maximum': %s > %s"
                    % (errors.summarize(value), spec["maximum"]), path)

    if isinstance(value, str):
        if "minLength" in spec and len(value) < spec["minLength"]:
            _reject(errors.SRV_SCHEMA_VIOLATION,
                    "violates 'minLength': %d < %d" % (len(value), spec["minLength"]), path)
        if "maxLength" in spec and len(value) > spec["maxLength"]:
            _reject(errors.SRV_SCHEMA_VIOLATION,
                    "violates 'maxLength': %d > %d" % (len(value), spec["maxLength"]), path)
