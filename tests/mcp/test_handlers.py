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
from ruledsl_mcp import handlers, load_library  # noqa: E402

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


def assert_error(result, domain, code, name):
    assert_true(handlers.is_error(result), f"expected error object, got {result!r}")
    assert_eq(result["error_domain"], domain)
    assert_eq(result["error_code"], code)
    assert_eq(result["error_name"], name)
    assert_true(set(result) == {"error_domain", "error_code", "error_name", "message"},
                f"error object keys drifted: {sorted(result)}")


def make_temp_library(rules):
    """Build a verified temp library dict {rule_id: source} with the engine."""
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    manifest = {"manifest_version": 1, "rules": {}}
    for rule_id, source in rules.items():
        fname = f"{rule_id}.ruledsl.txt"
        data = source.encode("utf-8")
        (root / fname).write_bytes(data)
        manifest["rules"][rule_id] = {
            "file": fname, "sha256": hashlib.sha256(data).hexdigest(),
            "version": "1.0.0"}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return td, load_library(root, compiler=engine)


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
        assert_eq(set(r), {"rule_id", "version", "rule_sha256"})
        assert_eq(r["rule_sha256"], library.get(r["rule_id"]).rule_sha256)


@test("engine_info: engine-derived values read at runtime, no drift")
def _():
    info = handlers.engine_info(library, engine)
    raw = engine.version()
    assert_true(info["engine_version"] in raw, "engine_version not from version()")
    assert_true(f"abi={info['abi_level']}" in raw, "abi_level not from version()")
    assert_true(isinstance(info["bytecode_schema_version"], int),
                "bytecode_schema_version missing")
    assert_eq(info["decision_record_schema"], "mcp_decision_record_v0")
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
    assert_error(result, "server", 1, "SRV_UNKNOWN_RULE_ID")
    assert_eq(log.getvalue(), "", "failed call must not write")


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
        {"divzero": "rule r2 { when amount / d > 1; then allow; }"})
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

@test("transport smoke: server registers exactly the three contract tools")
def _():
    try:
        from mcp.server.mcpserver import MCPServer  # noqa: F401
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP  # noqa: F401
        except ImportError:
            raise SkipTest("mcp package not installed; transport wiring untested here")
    import asyncio
    from ruledsl_mcp import server as server_mod
    server = server_mod.build_server(library, engine, io.StringIO())
    tools = asyncio.run(server.list_tools())
    assert_eq(sorted(t.name for t in tools),
              ["engine_info", "evaluate_case", "list_rules"])


# ---------------------------------------------------------------------------

print(f"\n{_passed} passed, {_failed} failed, {_skipped} skipped")
if hasattr(engine, "close"):
    engine.close()
sys.exit(1 if _failed else 0)
