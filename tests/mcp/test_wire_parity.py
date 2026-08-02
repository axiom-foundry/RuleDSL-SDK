#!/usr/bin/env python3
"""Wire contract: the stdio path must behave exactly like a direct call.

Requires the engine library AND the `mcp` SDK. Run:

    RULEDSL_DLL=<path to ruledsl_capi.dll|.so> python tests/mcp/test_wire_parity.py

Why this suite exists separately from test_handlers.py: calling
server.call_tool() in-process does NOT exercise the transport. The MCP SDK
pre-parses string arguments with json.loads before the tool ever runs
(pre_parse_json in mcp/server/mcpserver/utilities/func_metadata.py), and that
step only happens on a real request. A defect that lives in the gap between
the wire and the handler is invisible to an in-process test - which is exactly
how fields='{"amount":1}' was accepted and logged as a decision.

Two things are pinned here, both over a real JSON-RPC/stdio session against a
subprocess server:

  1. PARITY - the same hostile call produces the same error object whether it
     arrives over the wire or goes straight to handlers.evaluate_case.
  2. RESPONSE SIZE - a rejection is small no matter how large the input, and
     "small" is measured in bytes of the actual response line, not characters
     of a message. Character caps cannot see JSON escaping: canonical_json
     uses ensure_ascii, so one emoji becomes twelve characters, and the error
     object travels twice in one response (escaped inside content[0].text and
     again as structuredContent).

     The bound covers TOOL ARGUMENTS. The JSON-RPC `id` is excluded on
     purpose: the protocol requires it to be echoed verbatim, so a caller
     sending a 1 MiB id gets a 1 MiB id back - its own data, not input the
     server echoed - and truncating it would destroy the correlation an id
     exists for. Bounding that is a transport request-size limit, out of
     scope here (design doc section 4.1). This suite therefore uses ordinary
     ids and measures what the server actually authors.

Same hand-rolled harness as the other suites (no pytest).
"""

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "bindings" / "python"))

from ruledsl_mcp import errors, handlers, load_library  # noqa: E402
from ruledsl_mcp.smoke import JsonRpcStdioClient  # noqa: E402

ENGINE_LIB = os.environ.get("RULEDSL_DLL", "")
RULES_DIR = REPO_ROOT / "rules"
NOW = 1700000000000

# The response must stay under 1 KiB however hostile the input (design doc
# section 9). Measured on the raw line, envelope included.
MAX_RESPONSE_BYTES = 1024

_passed = 0
_failed = 0


def test(name):
    def wrap(fn):
        global _passed, _failed
        try:
            fn()
            _passed += 1
            print(f"  PASS  {name}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            _failed += 1
            print(f"  FAIL  {name}: {exc}")
        return fn
    return wrap


def assert_eq(a, b, msg=""):
    if a != b:
        raise AssertionError(f"expected {b!r}, got {a!r}" + (f" ({msg})" if msg else ""))


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(msg or "assertion failed")


# ---------------------------------------------------------------------------
# Hostile corpus - one table, driven down both paths
# ---------------------------------------------------------------------------

BIG = "x" * (1024 * 1024)
BACKSLASH = chr(92)

# (label, arguments). Every one of these must be refused identically by the
# wire and by a direct call.
PARITY_CASES = [
    ("fields as a JSON-encoded object string",
     {"rule_id": "allow_small", "fields": '{"amount":1}', "now_utc_ms": NOW}),
    ("fields as a JSON-encoded array string",
     {"rule_id": "allow_small", "fields": "[1,2]", "now_utc_ms": NOW}),
    ("fields as a number",
     {"rule_id": "allow_small", "fields": 1, "now_utc_ms": NOW}),
    ("rule_id as a number",
     {"rule_id": 7, "fields": {"amount": 1}, "now_utc_ms": NOW}),
    ("rule_id empty",
     {"rule_id": "", "fields": {"amount": 1}, "now_utc_ms": NOW}),
    ("rule_id oversized",
     {"rule_id": BIG, "fields": {"amount": 1}, "now_utc_ms": NOW}),
    ("rule_id unknown",
     {"rule_id": "no_such_rule", "fields": {"amount": 1}, "now_utc_ms": NOW}),
    # JSON-looking strings. These are ordinary strings a caller can send, and
    # the SDK's pre_parse_json used to turn them into None / {} / [1] before
    # the handler saw them - so the wire said "rule_id must be a string" where
    # a direct call said "unknown rule id".
    ("rule_id that looks like JSON null",
     {"rule_id": "null", "fields": {"amount": 1}, "now_utc_ms": NOW}),
    ("rule_id that looks like a JSON object",
     {"rule_id": "{}", "fields": {"amount": 1}, "now_utc_ms": NOW}),
    ("rule_id that looks like a JSON array",
     {"rule_id": "[1]", "fields": {"amount": 1}, "now_utc_ms": NOW}),
    ("now_utc_ms that looks like JSON null",
     {"rule_id": "allow_small", "fields": {"amount": 1}, "now_utc_ms": "null"}),
    ("now_utc_ms that looks like a JSON object",
     {"rule_id": "allow_small", "fields": {"amount": 1}, "now_utc_ms": "{}"}),
    ("now_utc_ms that looks like a JSON array",
     {"rule_id": "allow_small", "fields": {"amount": 1}, "now_utc_ms": "[1]"}),
    ("fields that looks like JSON null",
     {"rule_id": "allow_small", "fields": "null", "now_utc_ms": NOW}),
    ("now_utc_ms as a numeric string",
     {"rule_id": "allow_small", "fields": {"amount": 1}, "now_utc_ms": "1700000000000"}),
    ("now_utc_ms fractional",
     {"rule_id": "allow_small", "fields": {"amount": 1}, "now_utc_ms": NOW + 0.5}),
    ("now_utc_ms negative",
     {"rule_id": "allow_small", "fields": {"amount": 1}, "now_utc_ms": -1}),
    ("now_utc_ms beyond 2**53-1",
     {"rule_id": "allow_small", "fields": {"amount": 1}, "now_utc_ms": 2 ** 53}),
    ("now_utc_ms missing",
     {"rule_id": "allow_small", "fields": {"amount": 1}, "now_utc_ms": None}),
    ("now_utc_ms as a reserved field",
     {"rule_id": "allow_small", "fields": {"amount": 1, "now_utc_ms": NOW},
      "now_utc_ms": NOW}),
    ("field value with NUL",
     {"rule_id": "allow_small", "fields": {"amount": 1, "c": "TR\x00KP"},
      "now_utc_ms": NOW}),
    ("field name with NUL",
     {"rule_id": "allow_small", "fields": {"amount": 1, "a\x00b": 1},
      "now_utc_ms": NOW}),
    ("integer beyond 2**53-1",
     {"rule_id": "allow_small", "fields": {"amount": 2 ** 53 + 1}, "now_utc_ms": NOW}),
    ("string field where a number is declared",
     {"rule_id": "allow_small", "fields": {"amount": "2000"}, "now_utc_ms": NOW}),
    ("undeclared field",
     {"rule_id": "allow_small", "fields": {"amount": 1, "extra": 1}, "now_utc_ms": NOW}),
    ("oversized field value",
     {"rule_id": "allow_small", "fields": {"amount": 1, "c": BIG}, "now_utc_ms": NOW}),
    ("nested object as a field value",
     {"rule_id": "allow_small", "fields": {"amount": {"nested": 1}}, "now_utc_ms": NOW}),
]

# Size cases: four expansion profiles x the input positions that reach an
# error message or a field path. ASCII alone would not prove the bound - the
# escaped forms are what blew past the old character caps.
SIZE_PROFILES = [
    ("ascii", "x" * 1048576),
    ("unicode", "\u00fc\u00e7" * 400000),
    ("control", "\x01\x02" * 400000),
    ("backslash", (BACKSLASH + '"') * 400000),
]


def size_cases():
    for profile, blob in SIZE_PROFILES:
        yield ("rule_id/" + profile,
               {"rule_id": blob, "fields": {"amount": 1}, "now_utc_ms": NOW})
        yield ("argument-name/" + profile,
               {"rule_id": "allow_small", "fields": {"amount": 1},
                "now_utc_ms": NOW, blob: 1})
        yield ("nul-field-name/" + profile,
               {"rule_id": "allow_small", "fields": {blob + "\x00x": 1},
                "now_utc_ms": NOW})
        yield ("field-value/" + profile,
               {"rule_id": "allow_small", "fields": {"amount": 1, "c": blob},
                "now_utc_ms": NOW})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

if not ENGINE_LIB or not Path(ENGINE_LIB).exists():
    print("RULEDSL_DLL must point at the engine library; got: %r" % ENGINE_LIB,
          file=sys.stderr)
    sys.exit(2)

_tmp = tempfile.TemporaryDirectory()
_wire_log = str(Path(_tmp.name) / "wire.jsonl")

_env = dict(os.environ)
_env["PYTHONPATH"] = str(REPO_ROOT / "bindings" / "python")
client = JsonRpcStdioClient(
    [sys.executable, "-m", "ruledsl_mcp.server",
     "--rules", str(RULES_DIR),
     "--decision-log", _wire_log,
     "--engine-lib", ENGINE_LIB],
    _env)
client.request("initialize", {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "wire-parity", "version": "0"}})
client.notify("notifications/initialized")

from ruledsl import RuleDSL  # noqa: E402  (after the server is up)

engine = RuleDSL(ENGINE_LIB)
library = load_library(str(RULES_DIR), compiler=engine)


def call_wire(arguments):
    """Call over the real transport; return (error_object_or_None, raw_bytes)."""
    result = client.request("tools/call",
                            {"name": "evaluate_case", "arguments": arguments})
    raw = len(client.last_raw.encode("utf-8"))
    structured = result.get("structuredContent")
    if result.get("isError"):
        assert_true(errors.is_error(structured),
                    "isError result carries no error object: %r" % (structured,))
        return structured, raw
    return None, raw


def call_direct(arguments, log):
    """Call the handler in-process with the same raw arguments."""
    result = handlers.evaluate_case(
        library, engine, log,
        arguments.get("rule_id"), arguments.get("fields"),
        arguments.get("now_utc_ms"))
    return result if errors.is_error(result) else None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@test("parity: every hostile call is refused identically on both paths")
def _():
    import io
    mismatches = []
    for label, arguments in PARITY_CASES:
        wire, _raw = call_wire(arguments)
        direct = call_direct(arguments, io.StringIO())
        if wire is None:
            mismatches.append("%s: the WIRE accepted it" % label)
            continue
        if direct is None:
            mismatches.append("%s: the DIRECT call accepted it" % label)
            continue
        if wire != direct:
            mismatches.append("%s:\n    wire   %s\n    direct %s"
                              % (label, errors.canonical_json(wire),
                                 errors.canonical_json(direct)))
    assert_true(not mismatches, "\n  " + "\n  ".join(mismatches))


@test("parity: a rejected call writes no decision record on either path")
def _():
    assert_eq(Path(_wire_log).read_text(encoding="utf-8"), "",
              "the server logged a record for a rejected call")


@test("bounds: the JSON-RPC id is echoed verbatim and is not counted")
def _():
    """Documenting the edge of the bound rather than pretending it is not
    there: the protocol requires the id to come back unchanged, so it is the
    caller's own data on the wire, and it is excluded from the 1 KiB claim."""
    big_id = "i" * 4096
    client._send({"jsonrpc": "2.0", "id": big_id, "method": "tools/call",
                  "params": {"name": "evaluate_case",
                             "arguments": {"rule_id": "nope", "fields": {},
                                           "now_utc_ms": NOW}}})
    while True:
        line = client._lines.get(timeout=30)
        payload = json.loads(line)
        if payload.get("id") == big_id:
            break
    assert_true(len(line.encode("utf-8")) > MAX_RESPONSE_BYTES,
                "the id was not echoed back in full")
    body = errors.canonical_json(payload["result"]["structuredContent"])
    assert_true(len(body.encode("utf-8")) <= 512,
                "the part the SERVER authored must still be small: %d" % len(body))


@test("bounds: no tool argument can inflate the response past 1 KiB")
def _():
    oversized = []
    for label, arguments in size_cases():
        error, raw = call_wire(arguments)
        if error is None:
            oversized.append("%s: accepted, not refused" % label)
        elif raw > MAX_RESPONSE_BYTES:
            oversized.append("%s: %d bytes on the wire" % (label, raw))
    assert_true(not oversized, "\n  " + "\n  ".join(oversized))


@test("bounds: the same bound holds for every case in the hostile corpus")
def _():
    oversized = [(label, raw) for label, arguments in PARITY_CASES
                 for _err, raw in [call_wire(arguments)]
                 if raw > MAX_RESPONSE_BYTES]
    assert_true(not oversized, repr(oversized))


@test("wire: a JSON-encoded fields string is refused, not silently parsed")
def _():
    """The single defect this suite was written for. The SDK's pre_parse_json
    turns a string argument into an object when the annotation is not `str`,
    and ours is `Any` - so this used to return a decision and log a record."""
    error, _raw = call_wire({"rule_id": "allow_small",
                             "fields": '{"amount":1}', "now_utc_ms": NOW})
    assert_true(error is not None, "the wire accepted a JSON-encoded fields string")
    assert_eq(error["error_domain"], "engine")
    assert_eq(error["error_code"], errors.AX_ERR_INVALID_ARGUMENT)
    assert_eq(error["field"], "fields")
    assert_eq(Path(_wire_log).read_text(encoding="utf-8"), "")


@test("wire: a valid call still succeeds and matches the direct result")
def _():
    import io
    arguments = {"rule_id": "block_extreme", "fields": {"amount": 30000.0},
                 "now_utc_ms": NOW}
    result = client.request("tools/call",
                            {"name": "evaluate_case", "arguments": arguments})
    assert_true(not result.get("isError"), "valid call reported isError: %r" % result)
    wire_record = result["structuredContent"]
    direct_record = handlers.evaluate_case(
        library, engine, io.StringIO(), "block_extreme", {"amount": 30000.0}, NOW)
    assert_eq(errors.canonical_json(wire_record),
              errors.canonical_json(direct_record),
              "wire and direct records differ")
    # And the wire path did log exactly one line for it.
    lines = Path(_wire_log).read_text(encoding="utf-8").splitlines()
    assert_eq(len(lines), 1)
    assert_eq(json.loads(lines[0]), wire_record)


@test("wire: an integral-float clock yields the identical record")
def _():
    """1700000000000 and 1700000000000.0 are the same instant, and the wire is
    where the two spellings actually differ - JSON has one number type."""
    records = []
    for spelling in (NOW, float(NOW)):
        result = client.request("tools/call", {
            "name": "evaluate_case",
            "arguments": {"rule_id": "allow_small", "fields": {"amount": 1.0},
                          "now_utc_ms": spelling}})
        assert_true(not result.get("isError"), repr(result))
        records.append(errors.canonical_json(result["structuredContent"]))
    assert_eq(records[0], records[1], "the two spellings produced different records")
    assert_true('"now_utc_ms":1700000000000,' in records[0], records[0][:200])


@test("wire: an undeclared argument is refused by name")
def _():
    error, raw = call_wire({"rule_id": "allow_small", "fields": {"amount": 1},
                            "now_utc_ms": NOW, "bogus": 1})
    assert_eq(error["error_domain"], "server")
    assert_eq(error["error_code"], errors.SRV_UNKNOWN_ARGUMENT)
    assert_eq(error["field"], "bogus")
    assert_true(raw <= MAX_RESPONSE_BYTES, raw)


# ---------------------------------------------------------------------------

print(f"\n{_passed} passed, {_failed} failed")
client.close()
engine.close()
_tmp.cleanup()
sys.exit(1 if _failed else 0)
