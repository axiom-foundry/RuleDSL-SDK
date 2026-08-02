"""Server-domain error registry and the transport-free failure carrier.

Design contract: docs/design/mcp_server_v0.md section 5.

Two domains. The `engine` domain passes AXErrorCode through verbatim - the
server never remaps, collapses, or renames an engine code, and forwards
unknown ones rather than rejecting them. The `server` domain covers conditions
the engine cannot see from where it sits; those codes are stable, append-only,
and never reused.

This module imports nothing from the package, so library.py, handlers.py,
validate.py and server.py can all depend on it without a cycle, and it stays
importable with no engine and no MCP SDK present.
"""

import json

ENGINE_DOMAIN = "engine"
SERVER_DOMAIN = "server"

# Server-domain codes. APPEND ONLY - a code that shipped is never reused for a
# different meaning, because published decision logs and client branches refer
# to them by number.
SRV_UNKNOWN_RULE_ID = 1
SRV_RESERVED_FIELD = 2
SRV_FIELDS_TOO_LARGE = 3
SRV_UNSAFE_FIELD_VALUE = 4
SRV_FIELD_NAME_INVALID = 5
SRV_SCHEMA_VIOLATION = 6
SRV_NOW_UTC_MS_NOT_INTEGER = 7
SRV_INTERNAL = 8
SRV_UNKNOWN_ARGUMENT = 9

SERVER_ERROR_NAMES = {
    SRV_UNKNOWN_RULE_ID: "SRV_UNKNOWN_RULE_ID",
    SRV_RESERVED_FIELD: "SRV_RESERVED_FIELD",
    SRV_FIELDS_TOO_LARGE: "SRV_FIELDS_TOO_LARGE",
    SRV_UNSAFE_FIELD_VALUE: "SRV_UNSAFE_FIELD_VALUE",
    SRV_FIELD_NAME_INVALID: "SRV_FIELD_NAME_INVALID",
    SRV_SCHEMA_VIOLATION: "SRV_SCHEMA_VIOLATION",
    SRV_NOW_UTC_MS_NOT_INTEGER: "SRV_NOW_UTC_MS_NOT_INTEGER",
    SRV_INTERNAL: "SRV_INTERNAL",
    SRV_UNKNOWN_ARGUMENT: "SRV_UNKNOWN_ARGUMENT",
}

# Engine codes the server raises for conditions the engine defines but cannot
# observe from where it sits (section 3: omission of now_utc_ms is ALWAYS a
# validation error, even for rules that never read the clock).
AX_ERR_INVALID_ARGUMENT = 1
AX_ERR_MISSING_NOW_UTC_MS = 4
AX_ERR_NOW_UTC_MS_NOT_NUMBER = 5
AX_ERR_NON_FINITE = 6

ENGINE_ERROR_NAMES = {
    AX_ERR_INVALID_ARGUMENT: "AX_ERR_INVALID_ARGUMENT",
    AX_ERR_MISSING_NOW_UTC_MS: "AX_ERR_MISSING_NOW_UTC_MS",
    AX_ERR_NOW_UTC_MS_NOT_NUMBER: "AX_ERR_NOW_UTC_MS_NOT_NUMBER",
    AX_ERR_NON_FINITE: "AX_ERR_NON_FINITE",
}

# An error message must never be inflated by the input it rejects: a caller
# that sends a 1 MiB field would otherwise get a 1 MiB error back.
MAX_MESSAGE_VALUE_CHARS = 64

# Cheap first-pass caps on the two caller-influenced fields.
MAX_MESSAGE_CHARS = 200
MAX_FIELD_PATH_CHARS = 64

# The BINDING bound, and the reason the two above are not enough: the caps that
# matter are on the SERIALIZED size in bytes, not on a character count.
#
# A failure travels twice in one MCP response - once as canonical JSON inside
# content[0].text (where it is escaped AGAIN, so every " and \ doubles) and
# once as structuredContent - plus the JSON-RPC envelope. And canonical_json
# uses ensure_ascii=True, so a single "u" becomes ü (6 bytes) and then
# \\u00fc (7 bytes) in the text copy: a 7x expansion that no character count
# can see.
#
# Budget at 256 bytes: 256 (structuredContent) + at most 2x escaped text copy
# (512) + envelope (~110) = ~878 bytes, under 1 KiB even in the worst case;
# ~640 bytes for ordinary ASCII. Do NOT raise this without redoing that
# arithmetic - tests/mcp/test_wire_parity.py measures the real wire response.
MAX_ERROR_JSON_BYTES = 256

_TRUNCATED = "...(truncated)"


def canonical_json(obj):
    """Canonical serialization: byte-identical for equal inputs (section 3).

    allow_nan=False because Python's default emits the bare tokens NaN,
    Infinity and -Infinity, which are not JSON. A decision log holding them is
    unparseable by a conforming reader, and worse, the MCP transport encodes
    the same value as null - so the log and the response would disagree about
    the number the engine produced. Callers must refuse non-finite values
    before serializing; this raises ValueError rather than writing something no
    one can read back.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def summarize(value):
    """Render a value for an error message, bounded in length.

    The type is narrowed BEFORE repr() is called. CPython caps int->str
    conversion (4300 digits by default), so repr(10**5000) raises ValueError -
    an untyped failure raised while building the message for a typed one. A
    huge str is sliced first for the same reason in miniature: formatting a
    1 MiB name only to cut it is work done for nothing.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        if value.bit_length() > 256:
            return "an integer of about %d bits" % value.bit_length()
    elif isinstance(value, str) and len(value) > MAX_MESSAGE_VALUE_CHARS:
        return repr(value[:MAX_MESSAGE_VALUE_CHARS]) + "... (truncated)"
    text = repr(value)
    if len(text) <= MAX_MESSAGE_VALUE_CHARS:
        return text
    return text[:MAX_MESSAGE_VALUE_CHARS] + "... (truncated)"


def _clip(text, limit):
    """Character-level first pass. ASCII marker on purpose: a non-ASCII one
    would itself expand to six bytes per character in canonical JSON."""
    if not isinstance(text, str) or len(text) <= limit:
        return text
    return text[:limit] + _TRUNCATED


def _fit(err):
    """Shrink `message`, then `field`, until the object serializes within
    MAX_ERROR_JSON_BYTES.

    error_domain, error_code and error_name ALWAYS survive: they are what a
    client branches on, so they are never what gets sacrificed. Shrinking is
    deterministic, so two clients sending the same oversized call receive the
    same error.

    The marker's own length is subtracted from `keep`, so each round is
    STRICTLY shorter. Without that, `len // 2 + len(marker)` has a fixed point
    at 28 characters and the loop never terminates for inputs whose escaped
    form is still too large there - which is reachable, because ensure_ascii
    turns one emoji into twelve characters.
    """
    for key in ("message", "field"):
        while len(canonical_json(err).encode("utf-8")) > MAX_ERROR_JSON_BYTES:
            text = err[key]
            if not isinstance(text, str) or not text:
                break
            keep = len(text) // 2 - len(_TRUNCATED)
            err[key] = (text[:keep] + _TRUNCATED) if keep > 0 else None
    return err


def error(domain, code, name, message, field=None):
    """Build the section-5 error object, bounded in serialized size.

    `field` names what was rejected, as a dotted path into the call arguments
    ("fields.amount", "now_utc_ms"), or None for errors that are not scoped to
    one input. The key is ALWAYS present so a client never has to test for it.

    Bounding happens HERE, at construction, rather than at each call site: it
    covers every error this package can produce, including ones added later by
    someone who never reads this comment. An error must never be inflated by
    the input that caused it - see MAX_ERROR_JSON_BYTES.
    """
    return _fit({"error_domain": domain, "error_code": code, "error_name": name,
                 "message": _clip(message, MAX_MESSAGE_CHARS),
                 "field": _clip(field, MAX_FIELD_PATH_CHARS)})


def server_error(code, message, field=None):
    """Server-domain error; the name is looked up, never spelled at the call site."""
    return error(SERVER_DOMAIN, code, SERVER_ERROR_NAMES[code], message, field)


def engine_error(code, message, field=None, name=None):
    """Engine-domain error. `name` is required for codes this module does not
    know, because engine codes are forwarded verbatim including unknown ones."""
    if name is None:
        name = ENGINE_ERROR_NAMES[code]
    return error(ENGINE_DOMAIN, code, name, message, field)


def is_error(result):
    """True if a handler result is the section-5 error object."""
    return isinstance(result, dict) and "error_domain" in result


class ToolFailure(Exception):
    """Transport-agnostic carrier of the section-5 error object.

    handlers.py stays transport-free by contract: it RETURNS the error object.
    server.py converts it into an MCP failure result. This exception is the
    hand-off between the two, and is also what an unexpected exception inside a
    handler is converted into, so nothing escapes the error contract.
    """

    def __init__(self, err):
        self.error = err
        super().__init__(canonical_json(err))
