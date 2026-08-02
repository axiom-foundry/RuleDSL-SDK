"""RuleDSL MCP handler tests (Phase 2) - transport-free.

Covers: three tools happy path, canonical single-line JSONL record with
exactly 8 fields, byte-identical determinism, error paths (server codes
1-2, engine codes verbatim incl. unknown-code forwarding), no-write on
failure, privacy scan, and an optional transport smoke test (skipped if
the `mcp` package is not installed).

Requires the engine DLL and the public SDK python wrapper:
  RULEDSL_DLL      (default: <repo>/build/Release/ruledsl_capi.dll)
  RULEDSL_WRAPPER  (default: <repo>/../RuleDSL-SDK/bindings/python)
"""

import getpass
import hashlib
import io
import json
import os
import socket
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

sys.path.insert(0, str(REPO_ROOT / "bindings" / "python"))
import ruledsl_mcp  # noqa: E402
from ruledsl_mcp import errors, handlers, load_library, schemas  # noqa: E402

DLL_PATH = os.environ.get(
    "RULEDSL_DLL", str(REPO_ROOT / "build" / "Release" / "ruledsl_capi.dll"))
WRAPPER_DIR = os.environ.get(
    "RULEDSL_WRAPPER", str(REPO_ROOT.parent / "RuleDSL-SDK" / "bindings" / "python"))
sys.path.insert(0, WRAPPER_DIR)
from ruledsl import RuleDSL  # noqa: E402

RULES_DIR = REPO_ROOT / "rules"
NOW = 1700000000000

# ---------------------------------------------------------------------------
# Test infrastructure (same harness style as Tests/bindings)
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0
_skipped = 0
_errors = []


def test(name):
    def decorator(fn):
        global _passed, _failed, _skipped
        try:
            fn()
            _passed += 1
            print(f"  PASS  {name}")
        except SkipTest as e:
            _skipped += 1
            print(f"  SKIP  {name}: {e}")
        except Exception as e:
            _failed += 1
            _errors.append((name, e))
            print(f"  FAIL  {name}: {e}")
        return fn
    return decorator


class SkipTest(Exception):
    pass


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(msg or "condition is false")


def assert_eq(a, b, msg=""):
    if a != b:
        raise AssertionError(f"Expected {b!r}, got {a!r}" + (f" ({msg})" if msg else ""))


def canonical(obj):
    return handlers.canonical_json(obj)


def assert_error(result, domain, code, name, field=...):
    assert_true(handlers.is_error(result), f"expected error object, got {result!r}")
    assert_eq(result["error_domain"], domain)
    assert_eq(result["error_code"], code)
    assert_eq(result["error_name"], name)
    if field is not ...:
        assert_eq(result["field"], field, "field")
    assert_true(set(result) == {"error_domain", "error_code", "error_name",
                                "message", "field"},
                f"error object keys drifted: {sorted(result)}")


AMOUNT_ONLY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["amount"],
    "properties": {"amount": {"type": "number"}},
}


_USE_ENGINE = object()


def make_temp_library(rules, input_schema=AMOUNT_ONLY_SCHEMA, compiler=_USE_ENGINE):
    """Build a verified temp library dict {rule_id: source} with the engine.

    input_schema may be a single schema applied to every rule, or a dict
    {rule_id: schema}. Pass compiler=None to load without one (no bytecode).
    """
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    manifest = {"manifest_version": 2, "rules": {}}
    for rule_id, source in rules.items():
        fname = f"{rule_id}.ruledsl.txt"
        data = source.encode("utf-8")
        (root / fname).write_bytes(data)
        schema = (input_schema[rule_id]
                  if isinstance(input_schema, dict) and rule_id in input_schema
                  else input_schema)
        manifest["rules"][rule_id] = {
            "file": fname, "sha256": hashlib.sha256(data).hexdigest(),
            "version": "1.0.0", "input_schema": schema}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return td, load_library(root, compiler=engine if compiler is _USE_ENGINE else compiler)


engine = RuleDSL(DLL_PATH)
library = load_library(RULES_DIR, compiler=engine)

# ---------------------------------------------------------------------------
# list_rules / engine_info
# ---------------------------------------------------------------------------

@test("list_rules: manifest-declared ids with version + rule_sha256")
def _():
    result = handlers.list_rules(library)
    assert_eq([r["rule_id"] for r in result["rules"]],
              ["allow_small", "block_extreme", "velocity_limits"])
    for r in result["rules"]:
        assert_eq(set(r), {"rule_id", "version", "rule_sha256", "input_schema"})
        assert_eq(r["rule_sha256"], library.get(r["rule_id"]).rule_sha256)
        # Discovery must carry the input contract: evaluate_case rejects
        # anything the schema does not declare, so without it a caller cannot
        # construct an acceptable call.
        assert_eq(r["input_schema"], library.get(r["rule_id"]).input_schema)
        assert_eq(r["input_schema"]["additionalProperties"], False)


@test("engine_info: engine-derived values read at runtime, no drift")
def _():
    info = handlers.engine_info(library, engine)
    raw = engine.version()
    assert_true(info["engine_version"] in raw, "engine_version not from version()")
    assert_true(f"abi={info['abi_level']}" in raw, "abi_level not from version()")
    assert_true(isinstance(info["bytecode_schema_version"], int),
                "bytecode_schema_version missing")
    assert_eq(info["decision_record_schema"], "mcp_decision_record_v1")
    assert_eq(info["server_version"], ruledsl_mcp.__version__)
    assert_eq(info["manifest_sha256"],
              hashlib.sha256((RULES_DIR / "manifest.json").read_bytes()).hexdigest())


# ---------------------------------------------------------------------------
# evaluate_case - happy path
# ---------------------------------------------------------------------------

@test("evaluate: record returned + exactly one canonical log line + 8 fields")
def _():
    log = io.StringIO()
    record = handlers.evaluate_case(library, engine, log,
                                    "block_extreme", {"amount": 30000.0}, NOW)
    assert_true(not handlers.is_error(record), f"unexpected error: {record}")
    assert_eq(set(record), {"fields", "rule_id", "rule_sha256", "bytecode_sha256",
                            "decision", "decision_hash", "now_utc_ms",
                            "engine_version"})
    assert_eq(record["decision"]["action_type"], 1, "DECLINE action_type")
    assert_eq(record["decision"]["rule_name"], "block_extreme")
    assert_eq(record["rule_sha256"], library.get("block_extreme").rule_sha256)
    assert_eq(record["bytecode_sha256"], library.get("block_extreme").bytecode_sha256)
    lines = log.getvalue().splitlines()
    assert_eq(len(lines), 1, "exactly one JSONL line")
    assert_eq(lines[0], handlers.canonical_json(record), "line is canonical form")
    assert_eq(json.loads(lines[0]), record, "line round-trips")


@test("output schema: every tool's real result satisfies what it advertises")
def _():
    """The SDK validates a success against a model derived from the return
    annotation, NOT against the outputSchema attached to the tool - so what
    tools/list publishes was never actually enforced. handlers enforces it."""
    log = io.StringIO()
    schemas.check_output("list_rules", handlers.list_rules(library))
    schemas.check_output("engine_info", handlers.engine_info(library, engine))
    for rule_id, fields in (("allow_small", {"amount": 1.0}),
                            ("block_extreme", {"amount": 30000.0}),
                            ("velocity_limits", {"amount": 2500.0})):
        record = handlers.evaluate_case(library, engine, log, rule_id, fields, NOW)
        assert_true(not handlers.is_error(record), f"unexpected error: {record}")
        schemas.check_output("evaluate_case", record)


@test("output schema: a violating record is server/8 and is never logged")
def _():
    """A record that violates the advertised schema must not reach the log,
    which is why the check runs before the write rather than in the transport
    - otherwise the log would contradict the error the caller received."""
    log = io.StringIO()
    real = handlers._sha256_hex
    # decision_hash is declared as 64 lowercase hex; hand back something else.
    handlers._sha256_hex = lambda data: "NOT-A-SHA256"
    try:
        try:
            handlers.evaluate_case(library, engine, log, "allow_small",
                                   {"amount": 1.0}, NOW)
            raise AssertionError("the violation was not reported")
        except errors.ToolFailure as exc:
            assert_error(exc.error, "server", 8, "SRV_INTERNAL", None)
            assert_true("output schema" in exc.error["message"], exc.error["message"])
    finally:
        handlers._sha256_hex = real
    assert_eq(log.getvalue(), "", "a violating record must not be logged")
    # The server still works afterwards.
    record = handlers.evaluate_case(library, engine, log, "allow_small",
                                    {"amount": 1.0}, NOW)
    assert_true(not handlers.is_error(record), f"unexpected error: {record}")


@test("output schema: a non-finite number is refused before it can be logged")
def _():
    """NaN satisfies {"type": "number"}, and canonical JSON used to write the
    non-standard token NaN into the log while the transport encoded the same
    value as null - the log and the response disagreeing about the number the
    engine produced."""
    log = io.StringIO()

    class NanDecision:
        matched = True
        action_type = 0
        rule_name = "allow_small"
        amount = float("nan")
        currency = None
        window_count = float("inf")
        window_unit = None
        outputs = {"risk_score": float("nan")}

    class NanEngine:
        def version(self):
            return engine.version()

        def evaluate(self, *a, **kw):
            return NanDecision()

    try:
        handlers.evaluate_case(library, NanEngine(), log, "allow_small",
                               {"amount": 1.0}, NOW)
        raise AssertionError("a NaN decision was accepted")
    except errors.ToolFailure as exc:
        assert_error(exc.error, "server", 8, "SRV_INTERNAL", None)
        assert_true("finite" in exc.error["message"], exc.error["message"])
    assert_eq(log.getvalue(), "", "a non-serializable record must not be logged")


@test("output schema: a string with no UTF-8 form is refused before logging")
def _():
    """The log write would have succeeded - canonical JSON escapes a lone
    surrogate back to \\udXXX - while encoding the response to the client
    failed, so a decision would be recorded that the caller is told never
    happened."""
    log = io.StringIO()

    class SurrogateDecision:
        matched = True
        action_type = 0
        rule_name = "allow_small"
        amount = 0.0
        currency = None
        window_count = 0.0
        window_unit = None
        outputs = {"reason": "low\ud800value"}

    class SurrogateEngine:
        def version(self):
            return engine.version()

        def evaluate(self, *a, **kw):
            return SurrogateDecision()

    try:
        handlers.evaluate_case(library, SurrogateEngine(), log, "allow_small",
                               {"amount": 1.0}, NOW)
        raise AssertionError("a lone-surrogate decision was accepted")
    except errors.ToolFailure as exc:
        assert_error(exc.error, "server", 8, "SRV_INTERNAL", None)
        assert_true("UTF-8" in exc.error["message"], exc.error["message"])
    assert_eq(log.getvalue(), "")


@test("canonical JSON refuses non-finite numbers rather than emitting NaN")
def _():
    for bad in (float("nan"), float("inf"), float("-inf")):
        try:
            handlers.canonical_json({"x": bad})
        except ValueError:
            continue
        raise AssertionError("canonical_json emitted a non-JSON token for %r" % bad)


@test("determinism: identical calls yield byte-identical records")
def _():
    log = io.StringIO()
    handlers.evaluate_case(library, engine, log, "velocity_limits",
                           {"amount": 2500.0}, NOW)
    handlers.evaluate_case(library, engine, log, "velocity_limits",
                           {"amount": 2500.0}, NOW)
    lines = log.getvalue().splitlines()
    assert_eq(len(lines), 2)
    assert_eq(lines[0], lines[1], "records not byte-identical")


# ---------------------------------------------------------------------------
# evaluate_case - error paths (no record on failure)
# ---------------------------------------------------------------------------

@test("error: unknown rule_id -> SRV_UNKNOWN_RULE_ID=1, log untouched")
def _():
    log = io.StringIO()
    result = handlers.evaluate_case(library, engine, log,
                                    "no_such_rule", {"amount": 1.0}, NOW)
    assert_error(result, "server", 1, "SRV_UNKNOWN_RULE_ID", "rule_id")
    assert_eq(log.getvalue(), "", "failed call must not write")


# ---------------------------------------------------------------------------
# Input validation - the audit regressions
# ---------------------------------------------------------------------------

KYC_SOURCE = (REPO_ROOT / "examples" / "04_kyc_compliance" / "rules.rule").read_text(
    encoding="utf-8")

# Every field the rule reads is required. The engine raises UNKNOWN_PATH for a
# field a rule references but the case omits, so declaring them required turns
# that runtime surprise into a schema rejection naming the missing field.
KYC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["amount", "is_verified", "is_new_device", "ip_country", "email"],
    "properties": {
        "amount": {"type": "number", "minimum": 0},
        "is_verified": {"type": "boolean"},
        "is_new_device": {"type": "boolean"},
        "ip_country": {"type": "string", "maxLength": 8},
        "email": {"type": "string", "maxLength": 320},
    },
}

KYC_CASE = {
    "amount": 2000.0,
    "is_verified": False,
    "is_new_device": True,
    "ip_country": "TR",
    "email": "customer@example.com",
}


@test("fail-open regression: a numeric string is refused, not silently allowed")
def _():
    # THE finding. An audit ran a KYC rule twice with the same case:
    #   amount 2000.0  -> REVIEW / new_device_review
    #   amount "2000"  -> ALLOW  / default_allow
    # Shipped v0.9 makes cross-type comparisons return false with NO error and
    # applies no static type checking (docs/language/conformance_status_v0_9.md,
    # SEM-0018 and TYP-0003/0004), so the string matched no threshold and fell
    # through to the catch-all rule. The engine was deterministic and correct;
    # the input was never checked. Now it cannot get that far.
    td, kyc = make_temp_library({"kyc": KYC_SOURCE}, input_schema=KYC_SCHEMA)
    with td:
        log = io.StringIO()
        good = handlers.evaluate_case(kyc, engine, log, "kyc", KYC_CASE, NOW)
        assert_true(not handlers.is_error(good), f"typed case rejected: {good}")
        assert_eq(len(log.getvalue().splitlines()), 1, "one record for one decision")
        # The audit's reference outcome for this case.
        assert_eq(good["decision"]["rule_name"], "new_device_review")

        log = io.StringIO()
        bad = handlers.evaluate_case(kyc, engine, log, "kyc",
                                     dict(KYC_CASE, amount="2000"), NOW)
        assert_error(bad, "server", 6, "SRV_SCHEMA_VIOLATION", "fields.amount")
        assert_eq(log.getvalue(), "", "a refused call must not write a record")
        # And explicitly: it did NOT quietly become the catch-all decision.
        assert_true("decision" not in bad,
                    "a rejected call must not produce a decision at all")


@test("fail-open regression: a field the rule reads cannot be silently omitted")
def _():
    # The rule references ip_country; omitting it used to reach the engine and
    # surface as a runtime UNKNOWN_PATH mid-evaluation. Declared required, it is
    # a schema rejection that names the field before anything runs.
    td, kyc = make_temp_library({"kyc": KYC_SOURCE}, input_schema=KYC_SCHEMA)
    with td:
        log = io.StringIO()
        partial = {k: v for k, v in KYC_CASE.items() if k != "ip_country"}
        result = handlers.evaluate_case(kyc, engine, log, "kyc", partial, NOW)
        assert_error(result, "server", 6, "SRV_SCHEMA_VIOLATION", "fields.ip_country")
        assert_eq(log.getvalue(), "")


@test("fidelity: a NUL-containing string is refused; no record can carry one")
def _():
    # "TR\x00KP" was recorded in full while the engine saw only "TR" and
    # matched a rule on it.
    log = io.StringIO()
    result = handlers.evaluate_case(library, engine, log, "velocity_limits",
                                    {"amount": 100.0, "country": "TR\x00KP"}, NOW)
    assert_error(result, "server", 4, "SRV_UNSAFE_FIELD_VALUE", "fields.country")
    assert_eq(log.getvalue(), "")
    assert_true("\\u0000" not in canonical(result) and "\x00" not in canonical(result))


@test("fidelity: an integer beyond 2**53-1 is refused")
def _():
    # 9007199254740993 stayed verbatim in the log while the engine evaluated
    # 9007199254740992.
    log = io.StringIO()
    result = handlers.evaluate_case(library, engine, log, "velocity_limits",
                                    {"amount": 2 ** 53 + 1}, NOW)
    assert_error(result, "server", 4, "SRV_UNSAFE_FIELD_VALUE", "fields.amount")
    assert_eq(log.getvalue(), "")


@test("bounds: a 1 MiB field is refused and cannot inflate the response or the log")
def _():
    # An audit sent a 1 MiB unused field and got a ~1.049 MiB MCP response and
    # a ~1.049 MiB log line.
    log = io.StringIO()
    result = handlers.evaluate_case(
        library, engine, log, "velocity_limits",
        {"amount": 100.0, "padding": "x" * (1024 * 1024)}, NOW)
    assert_error(result, "server", 3, "SRV_FIELDS_TOO_LARGE", "fields.padding")
    assert_eq(log.getvalue(), "")
    assert_true(len(canonical(result)) < 1024,
                f"response scales with the rejected input: {len(canonical(result))} bytes")


@test("schema: undeclared and missing fields are refused")
def _():
    log = io.StringIO()
    result = handlers.evaluate_case(library, engine, log, "velocity_limits",
                                    {"amount": 100.0, "ghost": 1.0}, NOW)
    assert_error(result, "server", 6, "SRV_SCHEMA_VIOLATION", "fields.ghost")
    result = handlers.evaluate_case(library, engine, log, "velocity_limits", {}, NOW)
    assert_error(result, "server", 6, "SRV_SCHEMA_VIOLATION", "fields.amount")
    assert_eq(log.getvalue(), "")


@test("clock: numeric-string and fractional now_utc_ms are refused")
def _():
    log = io.StringIO()
    result = handlers.evaluate_case(library, engine, log, "allow_small",
                                    {"amount": 1.0}, "1700000000000")
    assert_error(result, "engine", 5, "AX_ERR_NOW_UTC_MS_NOT_NUMBER", "now_utc_ms")
    result = handlers.evaluate_case(library, engine, log, "allow_small",
                                    {"amount": 1.0}, NOW + 0.5)
    assert_error(result, "server", 7, "SRV_NOW_UTC_MS_NOT_INTEGER", "now_utc_ms")
    result = handlers.evaluate_case(library, engine, log, "allow_small",
                                    {"amount": 1.0}, 2 ** 53)
    assert_error(result, "server", 7, "SRV_NOW_UTC_MS_NOT_INTEGER", "now_utc_ms")
    # The advertised schema declares minimum: 0; honouring a wider range than
    # the one published is the same defect as publishing one we do not honour.
    result = handlers.evaluate_case(library, engine, log, "allow_small",
                                    {"amount": 1.0}, -1)
    assert_error(result, "server", 7, "SRV_NOW_UTC_MS_NOT_INTEGER", "now_utc_ms")
    assert_eq(log.getvalue(), "")


@test("clock: an integral float produces a byte-identical record to the int")
def _():
    """1700000000000 and 1700000000000.0 are the same instant. Before
    normalization the record carried the float verbatim, so the two calls
    logged different lines for the same evaluation - and the record claimed a
    schema (mcp_decision_record_v1) that promises a JSON integer."""
    log_int, log_float = io.StringIO(), io.StringIO()
    from_int = handlers.evaluate_case(library, engine, log_int, "allow_small",
                                      {"amount": 1.0}, NOW)
    from_float = handlers.evaluate_case(library, engine, log_float, "allow_small",
                                        {"amount": 1.0}, float(NOW))
    assert_eq(type(from_float["now_utc_ms"]), int)
    assert_eq(canonical(from_int), canonical(from_float))
    assert_eq(log_int.getvalue(), log_float.getvalue())
    assert_true('"now_utc_ms":1700000000000,' in log_float.getvalue(),
                "record should carry a JSON integer: " + log_float.getvalue()[:200])


@test("error: a bytecode-less library reports server/8, not a bare RuntimeError")
def _():
    # Previously a RuntimeError that escaped the error contract entirely.
    td, no_bytecode = make_temp_library({"r": "rule r { when amount > 1; then allow; }"},
                                        compiler=None)
    with td:
        log = io.StringIO()
        result = handlers.evaluate_case(no_bytecode, engine, log, "r",
                                        {"amount": 5.0}, NOW)
        assert_error(result, "server", 8, "SRV_INTERNAL", None)
        assert_eq(log.getvalue(), "")


@test("error: a non-string rule_id is refused")
def _():
    log = io.StringIO()
    for bad in (None, 123, ["allow_small"], ""):
        result = handlers.evaluate_case(library, engine, log, bad, {"amount": 1.0}, NOW)
        assert_error(result, "engine", 1, "AX_ERR_INVALID_ARGUMENT", "rule_id")
    assert_eq(log.getvalue(), "")


@test("error: reserved field now_utc_ms in fields -> SRV_RESERVED_FIELD=2")
def _():
    log = io.StringIO()
    result = handlers.evaluate_case(library, engine, log, "allow_small",
                                    {"amount": 1.0, "now_utc_ms": 123}, NOW)
    assert_error(result, "server", 2, "SRV_RESERVED_FIELD")
    assert_eq(log.getvalue(), "")


@test("error: omitted now_utc_ms -> AX_ERR_MISSING_NOW_UTC_MS=4 (engine domain)")
def _():
    log = io.StringIO()
    result = handlers.evaluate_case(library, engine, log, "allow_small",
                                    {"amount": 1.0}, None)
    assert_error(result, "engine", 4, "AX_ERR_MISSING_NOW_UTC_MS")
    assert_eq(log.getvalue(), "")


@test("error: engine failure passes through verbatim (AX_ERR_DIV_ZERO=7)")
def _():
    td, temp_lib = make_temp_library(
        {"divzero": "rule r2 { when amount / d > 1; then allow; }"},
        input_schema={"type": "object", "additionalProperties": False,
                      "required": ["amount", "d"],
                      "properties": {"amount": {"type": "number"},
                                     "d": {"type": "number"}}})
    with td:
        log = io.StringIO()
        result = handlers.evaluate_case(temp_lib, engine, log, "divzero",
                                        {"amount": 5.0, "d": 0.0}, NOW)
        assert_error(result, "engine", 7, "AX_ERR_DIV_ZERO")
        assert_eq(log.getvalue(), "")


@test("error: unknown engine code is forwarded, not rejected")
def _():
    class FutureEngineError(Exception):
        code = 999
        code_name = "AX_ERR_FROM_THE_FUTURE"

    class StubEngine:
        def version(self):
            return "RuleDSL/9.9.9 (abi=9)"

        def evaluate(self, bytecode, fields, now_utc_ms=None):
            raise FutureEngineError("engine grew a new error")

    log = io.StringIO()
    result = handlers.evaluate_case(library, StubEngine(), log, "allow_small",
                                    {"amount": 1.0}, NOW)
    assert_error(result, "engine", 999, "AX_ERR_FROM_THE_FUTURE")
    assert_eq(log.getvalue(), "")


# ---------------------------------------------------------------------------
# Convention pinning (design doc section 4: shared hashes never disagree)
# ---------------------------------------------------------------------------

@test("convention pinning: decision_hash follows the replay_proof_v1 shape")
def _():
    log = io.StringIO()
    record = handlers.evaluate_case(library, engine, log, "block_extreme",
                                    {"amount": 30000.0}, NOW)
    d = record["decision"]
    tooling_shape = {
        "matched": d["matched"],
        "action_type": d["action_type"],
        "amount": d["amount"],
        "currency": d["currency"],
        "window_count": d["window_count"],
        "window_unit": d["window_unit"],
        "rule_name": d["rule_name"],
        "outputs": d["outputs"],
    }
    assert_eq(set(d), set(tooling_shape),
              "decision payload keys drifted from the replay_proof_v1 shape")
    expected = hashlib.sha256(
        handlers.canonical_json(tooling_shape).encode("utf-8")).hexdigest()
    assert_eq(record["decision_hash"], expected,
              "decision_hash no longer matches the pinned convention")


# ---------------------------------------------------------------------------
# Privacy (design doc section 4)
# ---------------------------------------------------------------------------

@test("privacy: record carries no username/hostname/cwd/path traces")
def _():
    log = io.StringIO()
    handlers.evaluate_case(library, engine, log, "allow_small",
                           {"amount": 5.0}, NOW)
    line = log.getvalue()
    for needle in (getpass.getuser(), socket.gethostname(), os.getcwd(),
                   str(REPO_ROOT), str(RULES_DIR)):
        if needle and needle in line:
            raise AssertionError(f"record leaks environment value: {needle!r}")


# ---------------------------------------------------------------------------
# Transport smoke (skipped when `mcp` is not installed)
# ---------------------------------------------------------------------------

def _require_mcp():
    try:
        from mcp.server.mcpserver import MCPServer  # noqa: F401
    except ImportError:
        raise SkipTest("mcp package not installed; transport wiring untested here")


def _build():
    from ruledsl_mcp import server as server_mod
    log = io.StringIO()
    return server_mod.build_server(library, engine, log), log


@test("transport: server registers exactly the three contract tools")
def _():
    _require_mcp()
    import asyncio
    server, _ = _build()
    tools = asyncio.run(server.list_tools())
    assert_eq(sorted(t.name for t in tools),
              ["engine_info", "evaluate_case", "list_rules"])


@test("transport: the advertised schemas are OURS, not the SDK's derived ones")
def _():
    # The detector for an SDK that renames or reorders the schema attributes:
    # build_server refuses to start if the write does not take, and this
    # compares what list_tools actually reports against the constants.
    _require_mcp()
    import asyncio
    from ruledsl_mcp import schemas
    server, _ = _build()
    tools = {t.name: t for t in asyncio.run(server.list_tools())}
    for name, (input_schema, output_schema) in schemas.TOOL_SCHEMAS.items():
        assert_eq(tools[name].input_schema, input_schema, f"{name} inputSchema")
        assert_eq(tools[name].output_schema, output_schema, f"{name} outputSchema")
    # The specific claim the design doc made all along while the code used float.
    assert_eq(tools["evaluate_case"].input_schema["properties"]["now_utc_ms"]["type"],
              "integer")


@test("transport: a successful call carries structuredContent with no wrapper")
def _():
    _require_mcp()
    import asyncio
    server, log = _build()
    result = asyncio.run(server.call_tool("evaluate_case", {
        "rule_id": "velocity_limits", "fields": {"amount": 30000.0},
        "now_utc_ms": NOW}))
    assert_true(not result.is_error, "happy path reported isError")
    record = result.structured_content
    assert_true("result" not in record,
                "the SDK wrapped the return value; clients would need to unwrap")
    assert_eq(set(record), set(handlers._RECORD_FIELDS))
    assert_eq(record["decision"]["rule_name"], "block_extreme")
    # now_utc_ms must survive the wire as an int, not become 1700000000000.0.
    assert_true(isinstance(record["now_utc_ms"], int)
                and not isinstance(record["now_utc_ms"], bool),
                f"now_utc_ms arrived as {type(record['now_utc_ms']).__name__}")
    assert_eq(len(log.getvalue().splitlines()), 1)


@test("transport: every failure is isError with the typed error as structuredContent")
def _():
    # Before, unknown-rule / reserved-field / engine errors all came back with
    # isError:false and an error-shaped payload, so an orchestrator that checked
    # only transport success counted them as decisions.
    _require_mcp()
    import asyncio
    server, log = _build()
    base = {"rule_id": "velocity_limits", "fields": {"amount": 1.0}, "now_utc_ms": NOW}
    cases = [
        ("unknown rule", dict(base, rule_id="nope"), "server", 1, "rule_id"),
        ("reserved field", dict(base, fields={"amount": 1.0, "now_utc_ms": 1}),
         "server", 2, "fields.now_utc_ms"),
        ("oversized field", dict(base, fields={"amount": 1.0, "p": "x" * (1 << 20)}),
         "server", 3, "fields.p"),
        ("NUL string", dict(base, fields={"amount": 1.0, "c": "TR\x00KP"}),
         "server", 4, "fields.c"),
        ("numeric string", dict(base, fields={"amount": "30000"}),
         "server", 6, "fields.amount"),
        ("fractional clock", dict(base, now_utc_ms=NOW + 0.5),
         "server", 7, "now_utc_ms"),
        ("numeric-string clock", dict(base, now_utc_ms=str(NOW)),
         "engine", 5, "now_utc_ms"),
        ("missing clock", {k: v for k, v in base.items() if k != "now_utc_ms"},
         "engine", 4, "now_utc_ms"),
    ]
    for label, args, domain, code, field in cases:
        result = asyncio.run(server.call_tool("evaluate_case", args))
        assert_true(result.is_error, f"{label}: reported as success")
        err = result.structured_content
        assert_eq(err["error_domain"], domain, label)
        assert_eq(err["error_code"], code, label)
        assert_eq(err["field"], field, label)
        # The failure is also readable as text, for clients that only render it.
        assert_eq(json.loads(result.content[0].text), err, label)
    assert_eq(log.getvalue(), "", "a failed call must not write a record")


@test("transport: an undeclared argument is refused, never silently dropped")
def _():
    # The SDK's generated argument model ignores extras, so a misspelled
    # now_utc_ms would arrive as "absent" with the stray key dropped.
    _require_mcp()
    import asyncio
    from ruledsl_mcp import errors as err_mod
    server, log = _build()
    result = asyncio.run(server.call_tool("evaluate_case", {
        "rule_id": "velocity_limits", "fields": {"amount": 1.0},
        "now_utc_ms": NOW, "bogus": 1}))
    assert_true(result.is_error, "undeclared argument accepted")
    err = result.structured_content
    assert_eq(err["error_code"], err_mod.SRV_UNKNOWN_ARGUMENT)
    assert_eq(err["error_name"], "SRV_UNKNOWN_ARGUMENT")
    assert_eq(err["field"], "bogus")
    assert_eq(log.getvalue(), "")


@test("transport: a rejected 1 MiB field cannot inflate the response")
def _():
    _require_mcp()
    import asyncio
    server, _ = _build()
    result = asyncio.run(server.call_tool("evaluate_case", {
        "rule_id": "velocity_limits",
        "fields": {"amount": 1.0, "p": "x" * (1 << 20)}, "now_utc_ms": NOW}))
    encoded = json.dumps(result.model_dump(by_alias=True), default=str)
    assert_true(len(encoded) < 2048,
                f"error response is {len(encoded)} bytes for a rejected input")


@test("transport: list_rules exposes each rule's input_schema")
def _():
    _require_mcp()
    import asyncio
    server, _ = _build()
    result = asyncio.run(server.call_tool("list_rules", {}))
    assert_true(not result.is_error)
    for entry in result.structured_content["rules"]:
        assert_eq(entry["input_schema"],
                  library.get(entry["rule_id"]).input_schema)


# ---------------------------------------------------------------------------

print(f"\n{_passed} passed, {_failed} failed, {_skipped} skipped")
if hasattr(engine, "close"):
    engine.close()
sys.exit(1 if _failed else 0)
