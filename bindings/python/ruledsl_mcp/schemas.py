"""Hand-written MCP tool schemas. Pure data, stdlib only.

Design contract: docs/design/mcp_server_v0.md sections 2.5 and 9.

The MCP SDK derives an inputSchema from a tool function's annotations. That
derivation is wrong for this server in two ways, which is why these schemas are
written out here and attached explicitly in server.py:

  - A typed annotation makes Pydantic's lax mode COERCE. `now_utc_ms: float`
    turns the string "1700000000000" into a number, silently accepting exactly
    the input the server must refuse, and turns an int into a float, so the
    same evaluation produces a different decision record depending on whether
    it arrived over the wire or through a direct call.
  - `fields: dict` derives a bare {"type": "object"} that advertises no
    constraint at all, when the real contract is scalar values only, with each
    rule declaring its own schema (call list_rules).

`pattern` is used freely here: these are MCP wire schemas consumed by real
JSON Schema validators, unrelated to the small hand-rolled manifest subset in
validate.py, which excludes it deliberately.

This module imports nothing beyond the stdlib - not the engine, not the MCP
SDK - so tests can compare the advertised schemas against these constants
without either present.
"""

import math
import re

SHA256 = {"type": "string", "pattern": "^[0-9a-f]{64}$"}

NO_INPUT = {"type": "object", "properties": {}, "additionalProperties": False}

NOW_UTC_MS_SCHEMA = {
    "type": "integer",
    "minimum": 0,
    "maximum": 9007199254740991,
    "description": (
        "Explicit epoch milliseconds. Mandatory: the server never reads a clock, "
        "because a deterministic decision must be a pure function of explicit "
        "inputs. Must be a JSON integer - a numeric string is rejected rather "
        "than coerced, and a fractional value is rejected."
    ),
}

SCALAR_FIELD_VALUE = {
    "type": ["number", "string", "boolean", "null"],
    "description": (
        "Scalar only. Nested objects and arrays cannot cross the engine's value "
        "boundary and are rejected."
    ),
}

EVALUATE_CASE_INPUT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["rule_id", "fields", "now_utc_ms"],
    "properties": {
        "rule_id": {
            "type": "string",
            "minLength": 1,
            "description": "A rule id declared in the manifest; see list_rules.",
        },
        "fields": {
            "type": "object",
            "additionalProperties": SCALAR_FIELD_VALUE,
            "description": (
                "The case to evaluate. Each rule declares its own input_schema - "
                "call list_rules and satisfy that rule's schema exactly. Fields "
                "it does not declare are rejected, not ignored."
            ),
        },
        "now_utc_ms": NOW_UTC_MS_SCHEMA,
    },
}

DECISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["matched", "action_type", "rule_name", "amount", "currency",
                 "window_count", "window_unit", "outputs"],
    "properties": {
        "matched": {"type": "boolean"},
        # Numeric action_type, not the display name: the decision_hash is taken
        # over this shape (replay_proof_v1 convention).
        "action_type": {"type": "integer"},
        "rule_name": {"type": ["string", "null"]},
        "amount": {"type": "number"},
        "currency": {"type": ["string", "null"]},
        "window_count": {"type": "number"},
        "window_unit": {"type": ["string", "null"]},
        "outputs": {
            "type": "object",
            "additionalProperties": {"type": ["number", "string", "boolean", "null"]},
        },
    },
}

EVALUATE_CASE_OUTPUT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["fields", "rule_id", "rule_sha256", "bytecode_sha256",
                 "decision", "decision_hash", "now_utc_ms", "engine_version"],
    "properties": {
        "fields": {"type": "object", "description": "The case, verbatim as evaluated."},
        "rule_id": {"type": "string"},
        "rule_sha256": SHA256,
        "bytecode_sha256": SHA256,
        "decision": DECISION_SCHEMA,
        "decision_hash": SHA256,
        "now_utc_ms": {"type": "integer"},
        "engine_version": {"type": "string"},
    },
}

LIST_RULES_OUTPUT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["rules"],
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                # input_schema is part of the listing because it is the only way
                # a caller can construct a call this server will accept.
                "required": ["rule_id", "version", "rule_sha256", "input_schema"],
                "properties": {
                    "rule_id": {"type": "string"},
                    "version": {"type": "string"},
                    "rule_sha256": SHA256,
                    "input_schema": {
                        "type": "object",
                        "description": (
                            "The rule's declared input contract, from the hashed "
                            "manifest. Satisfy it exactly."
                        ),
                    },
                },
            },
        },
    },
}

ENGINE_INFO_OUTPUT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["engine_version", "abi_level", "bytecode_schema_version",
                 "decision_record_schema", "server_version", "manifest_sha256"],
    "properties": {
        "engine_version": {"type": "string"},
        "abi_level": {"type": ["integer", "null"]},
        "bytecode_schema_version": {"type": ["integer", "null"]},
        "decision_record_schema": {"type": "string"},
        "server_version": {"type": "string"},
        "manifest_sha256": SHA256,
    },
}

ERROR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["error_domain", "error_code", "error_name", "message", "field"],
    "properties": {
        "error_domain": {"type": "string", "enum": ["engine", "server"]},
        "error_code": {"type": "integer"},
        "error_name": {"type": "string"},
        "message": {"type": ["string", "null"]},
        "field": {
            "type": ["string", "null"],
            "description": (
                "Dotted path of the rejected input ('fields.amount', "
                "'now_utc_ms'), or null when the error is not scoped to one input."
            ),
        },
    },
}

# name -> (inputSchema, outputSchema). server.py attaches these to the
# registered tools and refuses to start if the transport SDK will not take them.
TOOL_SCHEMAS = {
    "list_rules": (NO_INPUT, LIST_RULES_OUTPUT),
    "evaluate_case": (EVALUATE_CASE_INPUT, EVALUATE_CASE_OUTPUT),
    "engine_info": (NO_INPUT, ENGINE_INFO_OUTPUT),
}


# ---------------------------------------------------------------------------
# Output conformance
# ---------------------------------------------------------------------------
#
# The SDK does NOT validate a successful result against the outputSchema
# advertised above. It attaches its own model derived from the tool function's
# return annotation (dict[str, Any]), and `tool.output_schema` - what
# tools/list shows a client - is a separate object it never consults. So a
# schema published here would be a promise nobody checked.
#
# We check it ourselves, and handlers does it BEFORE writing the decision log,
# so a violation cannot produce a record that contradicts the response.
#
# Unlike the manifest subset in validate.py, `pattern` is honoured here: these
# schemas are fixed constants written in this file, not caller-supplied data,
# so neither the ECMA-262 mismatch nor the ReDoS argument applies.

class OutputSchemaViolation(Exception):
    """A tool's own result does not satisfy the schema the server advertises."""


def check_output(tool_name, payload):
    """Raise OutputSchemaViolation if `payload` violates the tool's schema."""
    declared = TOOL_SCHEMAS.get(tool_name)
    if declared is None:
        raise OutputSchemaViolation("no schema declared for tool %r" % tool_name)
    _check(payload, declared[1], tool_name)


def check_against(schema, payload, path):
    """Check one payload against one schema.

    Exposed for the decision payload, which has to be validated BEFORE
    decision_hash is taken over it - hashing serializes, and serializing a
    non-finite number raises where a typed error is owed.
    """
    _check(payload, schema, path)


def _check(value, schema, path):
    # Representability first, before any schema keyword. A NaN satisfies
    # {"type": "number"} and a lone surrogate satisfies {"type": "string"},
    # yet neither can be transmitted: canonical JSON would write the
    # non-standard token NaN into the decision log while the transport encoded
    # the same value as null, and a lone surrogate cannot be encoded as UTF-8
    # at all - the log write would succeed and the response would fail, which
    # is the log/response split this check exists to prevent.
    if isinstance(value, float) and not math.isfinite(value):
        raise OutputSchemaViolation(
            "%s: %r is not a finite number and has no JSON representation" % (path, value))
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise OutputSchemaViolation(
                "%s: string is not encodable as UTF-8 (%s)" % (path, exc.reason))

    types = schema.get("type")
    if types is not None:
        types = types if isinstance(types, list) else [types]
        actual = _json_type(value)
        if not (actual in types
                or (actual == "integer" and "number" in types)):
            raise OutputSchemaViolation(
                "%s: expected %s, got %s" % (path, "/".join(types), actual))

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                raise OutputSchemaViolation("%s: missing required %r" % (path, name))
        additional = schema.get("additionalProperties", True)
        for name in sorted(value):
            if name in properties:
                _check(value[name], properties[name], "%s.%s" % (path, name))
            elif additional is False:
                raise OutputSchemaViolation("%s: undeclared key %r" % (path, name))
            else:
                # Recurse even where the schema constrains nothing (an open
                # object such as the record's `fields`): there is no keyword to
                # check, but the representability rules above still apply to
                # every value that will be serialized.
                _check(value[name], additional if isinstance(additional, dict) else {},
                       "%s.%s" % (path, name))
            # Keys are serialized too.
            _check(name, {}, "%s (key)" % path)

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            _check(item, schema["items"], "%s[%d]" % (path, index))

    if "enum" in schema and value not in schema["enum"]:
        raise OutputSchemaViolation(
            "%s: %r is not one of %r" % (path, value, schema["enum"]))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise OutputSchemaViolation(
                "%s: shorter than minLength %d" % (path, schema["minLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise OutputSchemaViolation(
                "%s: does not match %s" % (path, schema["pattern"]))


def _json_type(value):
    """bool before int: isinstance(True, int) is the trap in this file too."""
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
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__
