"""RuleDSL MCP tool handlers (Phase 2) - pure core, transport-free.

Design contract: docs/design/mcp_server_v0.md (sections 2-5).

Each handler is a plain function over (library, engine, log) with no MCP
knowledge and no third-party imports; server.py wires them to the MCP
transport. The engine is duck-typed (the public SDK RuleDSL wrapper):
version(), evaluate(bytecode, fields, now_utc_ms), check_compatibility().
Engine errors are recognized structurally as exceptions carrying an int
`code` and a `code_name` - passed through verbatim, never remapped;
unknown codes are forwarded, not rejected (section 5).

Failure returns the stable error object
{error_domain, error_code, error_name, message}; success returns the
tool's result. Only successful evaluations append to the decision log.
"""

import hashlib
import re

from . import errors, schemas, validate
from .errors import ENGINE_DOMAIN, SERVER_DOMAIN, canonical_json, is_error  # noqa: F401
from .library import UnknownRuleIdError
from .validate import FieldValidationError

# Bumped from mcp_decision_record_v0: now_utc_ms is always a JSON integer and
# every field value is guaranteed exactly representable, so the record and the
# engine's view of the input can no longer disagree.
DECISION_RECORD_SCHEMA = "mcp_decision_record_v1"

# The error registry lives in errors.py so it has exactly one home; these
# aliases keep the historical handler-level names working.
SRV_UNKNOWN_RULE_ID = errors.SRV_UNKNOWN_RULE_ID
SRV_RESERVED_FIELD = errors.SRV_RESERVED_FIELD

_error = errors.error

# fields keys reserved for explicit top-level parameters. A caller-supplied
# value here would be silently shadowed or overwritten - a hidden-behavior
# class - so the call is rejected before it reaches the engine.
RESERVED_FIELDS = ("now_utc_ms",)

# A manifest-declared rule id is a short identifier. Bounding it here keeps an
# oversized one from reaching library.get(), whose "unknown rule_id" message
# would otherwise be built from it (design doc section 9).
MAX_RULE_ID_BYTES = 128

_RECORD_FIELDS = ("fields", "rule_id", "rule_sha256", "bytecode_sha256",
                  "decision", "decision_hash", "now_utc_ms", "engine_version")

_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")
_ABI_RE = re.compile(r"abi=(\d+)")


def _sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def _conforming(tool_name, payload):
    """Return payload, having proved it satisfies the ADVERTISED outputSchema.

    The MCP SDK validates a successful result against a model derived from the
    tool function's return annotation, not against the schema attached to the
    tool - so what tools/list publishes was never actually enforced. It is
    enforced here.

    A violation is our defect, not the caller's: it becomes SRV_INTERNAL.
    """
    try:
        schemas.check_output(tool_name, payload)
    except schemas.OutputSchemaViolation as exc:
        raise errors.ToolFailure(errors.server_error(
            errors.SRV_INTERNAL,
            "result violates this server's advertised output schema: %s" % exc))
    return payload


def _is_engine_error(exc):
    return isinstance(getattr(exc, "code", None), int) and hasattr(exc, "code_name")


def _engine_versions(engine):
    """Parse engine_version + abi_level from the engine's own version string
    at call time - never copied into server code, so they cannot drift."""
    raw = engine.version()
    version = _VERSION_RE.search(raw)
    abi = _ABI_RE.search(raw)
    if not version:
        raise errors.ToolFailure(errors.server_error(
            errors.SRV_INTERNAL,
            "engine version string not parseable: %s" % errors.summarize(raw)))
    return version.group(1), (int(abi.group(1)) if abi else None)


def list_rules(library):
    """Tool 1 (section 2.1): manifest-declared rules only; no filesystem scan.

    Each entry carries the rule's input_schema: since evaluate_case rejects
    anything the schema does not declare, this listing is the only way a caller
    can construct a call the server will accept.
    """
    return _conforming("list_rules", {"rules": [
        {"rule_id": rule_id,
         "version": library.get(rule_id).version,
         "rule_sha256": library.get(rule_id).rule_sha256,
         "input_schema": library.get(rule_id).input_schema}
        for rule_id in library.rule_ids()]})


def engine_info(library, engine):
    """Tool 3 (section 2.3). Engine-derived values are read from the engine
    and binding at runtime (anti-drift); only schema id and server version
    originate here."""
    engine_version, abi_level = _engine_versions(engine)
    bytecode_schema_version = None
    for rule_id in library.rule_ids():
        bytecode = library.get(rule_id).bytecode
        if bytecode:
            bytecode_schema_version = engine.check_compatibility(bytecode)["axbc_version"]
            break
    from . import __version__ as server_version
    return _conforming("engine_info", {
        "engine_version": engine_version,
        "abi_level": abi_level,
        "bytecode_schema_version": bytecode_schema_version,
        "decision_record_schema": DECISION_RECORD_SCHEMA,
        "server_version": server_version,
        "manifest_sha256": library.manifest_sha256,
    })


def check_call_shape(tool_name, arguments):
    """Check the top-level shape of a call. Returns an error object or None.

    Transport-free, so server.py can run it on the RAW argument dict BEFORE
    the MCP SDK gets a chance to coerce anything, and evaluate_case can run
    the identical check for a direct in-process call. One implementation with
    two callers is what makes the wire and in-process paths agree by
    construction rather than by a test that has to notice when they drift.

    The reason this has to run early: the SDK pre-parses any string argument
    whose annotation is not `str` with json.loads (see pre_parse_json in
    mcp/server/mcpserver/utilities/func_metadata.py), so a caller sending
    fields='{"amount":1}' would have it silently turned into an object and
    accepted. Type discipline that runs after coercion is not type discipline.
    """
    if tool_name != "evaluate_case":
        return None
    rule_id = arguments.get("rule_id")
    fields = arguments.get("fields")

    if not isinstance(rule_id, str) or not rule_id:
        return errors.engine_error(
            errors.AX_ERR_INVALID_ARGUMENT,
            "rule_id must be a non-empty string, got %s" % type(rule_id).__name__,
            "rule_id")
    if len(rule_id.encode("utf-8", "surrogatepass")) > MAX_RULE_ID_BYTES:
        return errors.server_error(
            errors.SRV_FIELDS_TOO_LARGE,
            "rule_id is longer than %d bytes; a manifest-declared id is never "
            "this large" % MAX_RULE_ID_BYTES, "rule_id")
    if not isinstance(fields, dict):
        return errors.engine_error(
            errors.AX_ERR_INVALID_ARGUMENT,
            "fields must be an object, got %s" % type(fields).__name__, "fields")
    for reserved in RESERVED_FIELDS:
        if reserved in fields:
            return errors.server_error(
                errors.SRV_RESERVED_FIELD,
                "fields key %r is reserved for the explicit top-level parameter; "
                "silent overwrite is refused" % reserved, "fields.%s" % reserved)

    # The clock's RAW type, checked here rather than only in validate: the SDK
    # pre-parses a string argument with json.loads, so now_utc_ms="null" became
    # None and read as "omitted" (engine/4) over the wire while a direct call
    # correctly reported a non-number (engine/5). Same wording as
    # validate.validate_now_utc_ms, so the two can never disagree.
    now_utc_ms = arguments.get("now_utc_ms")
    if now_utc_ms is not None and (isinstance(now_utc_ms, bool)
                                   or not isinstance(now_utc_ms, (int, float))):
        return errors.engine_error(
            errors.AX_ERR_NOW_UTC_MS_NOT_NUMBER,
            "now_utc_ms must be a number, got %s" % type(now_utc_ms).__name__,
            "now_utc_ms")
    return None


def evaluate_case(library, engine, log, rule_id, fields, now_utc_ms):
    """Tool 2 (section 2.2): evaluate, append exactly one canonical JSONL
    line on success, return the decision record. Failed calls return the
    error object and write nothing (section 4)."""
    shape = check_call_shape("evaluate_case", {"rule_id": rule_id, "fields": fields,
                                               "now_utc_ms": now_utc_ms})
    if shape is not None:
        return shape

    try:
        entry = library.get(rule_id)
    except UnknownRuleIdError as exc:
        return errors.server_error(exc.server_error_code, str(exc), "rule_id")
    if entry.bytecode is None or entry.bytecode_sha256 is None:
        return errors.server_error(
            errors.SRV_INTERNAL,
            "rule %r has no bytecode: the library was loaded without a compiler; "
            "the server must load with one" % rule_id)

    # Validate BEFORE the engine runs and before anything is logged, so a
    # rejected call leaves no decision record. This is what turns a type
    # mistake into an error instead of a wrong decision: shipped v0.9 compares
    # across types silently (docs/language/conformance_status_v0_9.md), so an
    # unvalidated "2000" would not fail - it would quietly match nothing and
    # fall through to whatever rule catches everything.
    try:
        # Rebound to the NORMALIZED integer: 1700000000000 and
        # 1700000000000.0 are the same instant and must produce a
        # byte-identical record, not `...000` versus `...000.0`. Everything
        # below - the engine call and the record - uses this value.
        now_utc_ms = validate.validate_now_utc_ms(now_utc_ms)
        validate.validate_fields(fields, entry.input_schema)
    except FieldValidationError as exc:
        return exc.error

    try:
        decision = engine.evaluate(entry.bytecode, fields, now_utc_ms=now_utc_ms)
    except Exception as exc:
        if _is_engine_error(exc):
            return errors.engine_error(exc.code, str(exc), name=str(exc.code_name))
        raise

    # Payload shape is pinned to the replay_proof_v1 convention (published
    # evidence hashes are computed over this shape): action_type numeric,
    # not the display name "action". Section 4: the two schemas must never
    # disagree on shared hashes for the same evaluation.
    decision_payload = {
        "matched": decision.matched,
        "action_type": decision.action_type,
        "rule_name": decision.rule_name,
        "amount": decision.amount,
        "currency": decision.currency,
        "window_count": decision.window_count,
        "window_unit": decision.window_unit,
        "outputs": dict(decision.outputs),
    }
    # Checked before the hash, not after: decision_hash is taken over the
    # canonical serialization of this payload, and serializing a non-finite
    # number raises - an untyped failure at the moment a typed one is owed.
    try:
        schemas.check_against(schemas.DECISION_SCHEMA, decision_payload,
                              "evaluate_case.decision")
    except schemas.OutputSchemaViolation as exc:
        raise errors.ToolFailure(errors.server_error(
            errors.SRV_INTERNAL,
            "result violates this server's advertised output schema: %s" % exc))

    engine_version, _ = _engine_versions(engine)
    record = {
        "fields": fields,
        "rule_id": rule_id,
        "rule_sha256": entry.rule_sha256,
        "bytecode_sha256": entry.bytecode_sha256,
        "decision": decision_payload,
        "decision_hash": _sha256_hex(canonical_json(decision_payload).encode("utf-8")),
        "now_utc_ms": now_utc_ms,
        "engine_version": engine_version,
    }
    # Checked BEFORE the write, not after: a record that violates the schema
    # the server advertises must not exist in the log at all. Validating on the
    # way out of the transport instead would leave a logged record contradicting
    # the error the caller received. Subsumes the old field-set check, which was
    # a bare assert - stripped by `python -O`, i.e. absent in exactly the
    # configuration most likely to run in production.
    record = _conforming("evaluate_case", record)

    # NOTE (scope): this writes a decision RECORD, not an audit ledger.
    #
    # What it guarantees: in a successfully written record, `fields` and
    # `now_utc_ms` are exactly what the engine evaluated - validation above
    # refuses every value that would reach the engine altered, so the record
    # and the decision can no longer describe different inputs.
    #
    # What it does NOT provide, and what this layer does not claim: atomicity
    # or ordering between concurrent writers, durability against a partial
    # write (there is a flush, no fsync), sequence/request/principal/tenant
    # identity, a hash over the whole record or a hash chain linking records,
    # any record of failed calls, PII redaction, or size and rotation limits.
    # See docs/design/mcp_server_v0.md section 4.
    log.write(canonical_json(record) + "\n")
    if hasattr(log, "flush"):
        log.flush()
    return record
