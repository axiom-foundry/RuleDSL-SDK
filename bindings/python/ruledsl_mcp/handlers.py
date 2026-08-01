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
import json
import re

from .library import UnknownRuleIdError

DECISION_RECORD_SCHEMA = "mcp_decision_record_v0"

ENGINE_DOMAIN = "engine"
SERVER_DOMAIN = "server"

# Server-domain error contract (design doc section 5): stable numeric
# codes, append-only, never reused. Codes for conditions the engine
# cannot see; everything else passes through as engine-domain verbatim.
SRV_UNKNOWN_RULE_ID = 1
SRV_RESERVED_FIELD = 2

# Engine codes the server raises for conditions the engine defines but
# cannot observe from where it sits (section 3: omission of now_utc_ms is
# ALWAYS a validation error, even for rules that never read the clock).
_AX_ERR_MISSING_NOW_UTC_MS = 4
_AX_ERR_NOW_UTC_MS_NOT_NUMBER = 5

# fields keys reserved for explicit top-level parameters. A caller-supplied
# value here would be silently shadowed or overwritten - a hidden-behavior
# class - so the call is rejected before it reaches the engine.
RESERVED_FIELDS = ("now_utc_ms",)

_RECORD_FIELDS = ("fields", "rule_id", "rule_sha256", "bytecode_sha256",
                  "decision", "decision_hash", "now_utc_ms", "engine_version")

_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")
_ABI_RE = re.compile(r"abi=(\d+)")


def canonical_json(obj):
    """Canonical serialization: byte-identical for equal inputs (section 3)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def _error(domain, code, name, message):
    return {"error_domain": domain, "error_code": code,
            "error_name": name, "message": message}


def is_error(result):
    """True if a handler result is the section-5 error object."""
    return isinstance(result, dict) and "error_domain" in result


def _is_engine_error(exc):
    return isinstance(getattr(exc, "code", None), int) and hasattr(exc, "code_name")


def _engine_versions(engine):
    """Parse engine_version + abi_level from the engine's own version string
    at call time - never copied into server code, so they cannot drift."""
    raw = engine.version()
    version = _VERSION_RE.search(raw)
    abi = _ABI_RE.search(raw)
    if not version:
        raise RuntimeError(f"engine version string not parseable: {raw!r}")
    return version.group(1), (int(abi.group(1)) if abi else None)


def list_rules(library):
    """Tool 1 (section 2.1): manifest-declared rules only; no filesystem scan."""
    return {"rules": [
        {"rule_id": rule_id,
         "version": library.get(rule_id).version,
         "rule_sha256": library.get(rule_id).rule_sha256}
        for rule_id in library.rule_ids()]}


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
    return {
        "engine_version": engine_version,
        "abi_level": abi_level,
        "bytecode_schema_version": bytecode_schema_version,
        "decision_record_schema": DECISION_RECORD_SCHEMA,
        "server_version": server_version,
        "manifest_sha256": library.manifest_sha256,
    }


def evaluate_case(library, engine, log, rule_id, fields, now_utc_ms):
    """Tool 2 (section 2.2): evaluate, append exactly one canonical JSONL
    line on success, return the decision record. Failed calls return the
    error object and write nothing (section 4)."""
    if not isinstance(fields, dict):
        return _error(ENGINE_DOMAIN, 1, "AX_ERR_INVALID_ARGUMENT",
                      "fields must be an object")
    for reserved in RESERVED_FIELDS:
        if reserved in fields:
            return _error(SERVER_DOMAIN, SRV_RESERVED_FIELD, "SRV_RESERVED_FIELD",
                          f"fields key {reserved!r} is reserved for the explicit "
                          f"top-level parameter; silent overwrite is refused")
    if now_utc_ms is None:
        return _error(ENGINE_DOMAIN, _AX_ERR_MISSING_NOW_UTC_MS,
                      "AX_ERR_MISSING_NOW_UTC_MS",
                      "now_utc_ms is required and explicit; the server never "
                      "reads a clock (design doc section 3)")
    if isinstance(now_utc_ms, bool) or not isinstance(now_utc_ms, (int, float)):
        return _error(ENGINE_DOMAIN, _AX_ERR_NOW_UTC_MS_NOT_NUMBER,
                      "AX_ERR_NOW_UTC_MS_NOT_NUMBER",
                      f"now_utc_ms must be a number, got {type(now_utc_ms).__name__}")

    try:
        entry = library.get(rule_id)
    except UnknownRuleIdError as exc:
        return _error(SERVER_DOMAIN, exc.server_error_code, exc.server_error_name,
                      str(exc))
    if entry.bytecode is None or entry.bytecode_sha256 is None:
        raise RuntimeError(
            f"rule {rule_id!r} has no bytecode: library was loaded without a "
            f"compiler; the server must load with one")

    try:
        decision = engine.evaluate(entry.bytecode, fields, now_utc_ms=now_utc_ms)
    except Exception as exc:
        if _is_engine_error(exc):
            return _error(ENGINE_DOMAIN, exc.code, str(exc.code_name), str(exc))
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
    assert set(record) == set(_RECORD_FIELDS)

    log.write(canonical_json(record) + "\n")
    if hasattr(log, "flush"):
        log.flush()
    return record
