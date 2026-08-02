"""RuleDSL MCP e2e smoke client - stdlib-only, no `mcp` dependency.

Run as a module: python -m ruledsl_mcp.smoke --engine-lib <lib>

Speaks raw JSON-RPC over stdio (newline-delimited) to a `ruledsl_mcp.server`
subprocess and asserts the v0 contract end to end:

  1. initialize handshake answers with server name "ruledsl-mcp" (and the
     package's own version when the transport SDK reports one)
  2. tools/list exposes exactly the three contract tools (closed list)
  3. evaluate_case twice with identical input -> decision log holds exactly
     two byte-identical canonical JSONL lines
  4. reserved field now_utc_ms inside `fields` -> server/2 SRV_RESERVED_FIELD
     (rejected before the engine, nothing logged)

Exit code 0 = PASS, 1 = FAIL, 2 = usage/setup error. The server itself is
the real one (real engine, real rules); only the MCP *client* side is
re-implemented here so verification needs no MCP client package.

Pip path (self-contained, no repository checkout needed):
    python -m ruledsl_mcp.smoke --engine-lib /path/to/libruledsl_capi.so
--rules defaults to the packaged example library; --wrapper is only needed
when the `ruledsl` wrapper is NOT importable from this environment (e.g. a
bare checkout without the package installed).
"""

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from . import __version__ as SERVER_PACKAGE_VERSION
from .server import example_rules_dir

# Directory that contains the `ruledsl_mcp` package itself (site-packages on
# the pip path, bindings/python on a checkout). Prepended to the child
# server's PYTHONPATH so the spawned server always runs THIS package.
PKG_PARENT = Path(__file__).resolve().parent.parent

READ_TIMEOUT_S = 30
NOW_UTC_MS = 1700000000000
EXPECTED_TOOLS = ["engine_info", "evaluate_case", "list_rules"]


class SmokeFailure(Exception):
    pass


class JsonRpcStdioClient:
    """Minimal newline-delimited JSON-RPC client over a subprocess's stdio."""

    def __init__(self, cmd, env):
        self.proc = subprocess.Popen(
            cmd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        self._lines = queue.Queue()
        self._next_id = 0
        # The RAW response line for the last request. Response size is part of
        # the contract (design doc section 9) and the only honest way to measure
        # it is the bytes that actually crossed the pipe - a re-serialized dict
        # is a different string.
        self.last_raw = None
        self._reader = threading.Thread(target=self._pump_stdout, daemon=True)
        self._reader.start()
        self._stderr_chunks = []
        self._stderr_reader = threading.Thread(target=self._pump_stderr, daemon=True)
        self._stderr_reader.start()

    def _pump_stdout(self):
        for line in self.proc.stdout:
            line = line.strip()
            if line:
                self._lines.put(line)

    def _pump_stderr(self):
        for line in self.proc.stderr:
            self._stderr_chunks.append(line)

    def stderr_tail(self, max_lines=15):
        return "".join(self._stderr_chunks[-max_lines:])

    def _send(self, message):
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def notify(self, method, params=None):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def request(self, method, params=None):
        self._next_id += 1
        request_id = self._next_id
        message = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)
        while True:
            try:
                line = self._lines.get(timeout=READ_TIMEOUT_S)
            except queue.Empty:
                raise SmokeFailure(
                    f"timeout waiting for response to {method!r}; "
                    f"server stderr tail:\n{self.stderr_tail()}")
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                raise SmokeFailure(f"non-JSON line on server stdout: {line!r}")
            if payload.get("id") != request_id:
                continue  # server-initiated message or stale response
            self.last_raw = line
            if "error" in payload:
                raise SmokeFailure(f"{method} returned JSON-RPC error: {payload['error']}")
            return payload["result"]

    def close(self):
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
            self.proc.wait(timeout=10)


def tool_result_payload(result):
    """Extract the tool's return dict from an MCP tools/call result.

    The server declares an outputSchema and returns dict[str, Any], so the
    payload arrives unwrapped in structuredContent - on both success and
    failure. The {"result": ...} form is an SDK wrapping of bare-dict returns;
    it is treated as a hard failure rather than silently unwrapped, because
    clients would then have to guess which shape they got.
    """
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        if set(structured) == {"result"}:
            raise SmokeFailure(
                "structuredContent arrived wrapped as {'result': ...}; the "
                "server must return the payload unwrapped")
        return structured
    for item in result.get("content", []):
        if item.get("type") == "text":
            return json.loads(item["text"])
    raise SmokeFailure(f"tools/call result carries no payload: {result!r}")


def call_error(client, arguments, tool="evaluate_case"):
    """Call a tool expecting failure; return (isError, error object).

    The error object must be readable from structuredContent AND from the text
    block, and the two must agree - a client should not have to parse prose.
    """
    result = client.request("tools/call", {"name": tool, "arguments": arguments})
    payload = tool_result_payload(result)
    text_blocks = [item["text"] for item in result.get("content", [])
                   if item.get("type") == "text"]
    if text_blocks and json.loads(text_blocks[0]) != payload:
        raise SmokeFailure(
            "structuredContent and the text block disagree: "
            f"{payload!r} vs {text_blocks[0]!r}")
    return bool(result.get("isError")), payload


def check_error(client, label, arguments, domain, code, name, field):
    is_error, err = call_error(client, arguments)
    check(is_error, f"{label}: isError is true")
    check(err.get("error_domain") == domain and err.get("error_code") == code
          and err.get("error_name") == name and err.get("field") == field,
          f"{label}: {domain}/{code} {name} field={field} (got "
          f"{err.get('error_domain')}/{err.get('error_code')} "
          f"{err.get('error_name')} field={err.get('field')})")
    return err


def check(condition, message):
    if not condition:
        raise SmokeFailure(message)
    print(f"  ok  {message}")


def run_smoke(args):
    rules_dir = Path(args.rules).resolve() if args.rules else example_rules_dir()
    if rules_dir is None or not (Path(rules_dir) / "manifest.json").is_file():
        raise SmokeFailure(
            f"no usable rule library (looked at {rules_dir!r}); pass --rules")

    decision_log = Path(tempfile.mkdtemp(prefix="ruledsl_mcp_smoke_")) / "decisions.jsonl"

    env = dict(os.environ)
    pythonpath = [str(PKG_PARENT)]
    if args.wrapper:
        pythonpath.append(str(Path(args.wrapper).resolve()))
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [sys.executable, "-m", "ruledsl_mcp.server",
           "--rules", str(rules_dir),
           "--decision-log", str(decision_log),
           "--engine-lib", str(Path(args.engine_lib).resolve())]

    client = JsonRpcStdioClient(cmd, env)
    try:
        init = client.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ruledsl-smoke-client", "version": "0"},
        })
        server_info = init.get("serverInfo", {})
        check(server_info.get("name") == "ruledsl-mcp",
              f"handshake: serverInfo.name == 'ruledsl-mcp' (got {server_info.get('name')!r})")
        check(server_info.get("version") == SERVER_PACKAGE_VERSION,
              f"handshake: serverInfo.version == package version "
              f"{SERVER_PACKAGE_VERSION} (got {server_info.get('version')!r})")
        client.notify("notifications/initialized")

        tools = client.request("tools/list")
        by_name = {t["name"]: t for t in tools.get("tools", [])}
        names = sorted(by_name)
        check(names == EXPECTED_TOOLS,
              f"tools/list: exactly {EXPECTED_TOOLS} (got {names})")
        check(all(by_name[n].get("outputSchema") for n in EXPECTED_TOOLS),
              "tools/list: every tool advertises an outputSchema")
        now_schema = (by_name["evaluate_case"]["inputSchema"]
                      .get("properties", {}).get("now_utc_ms", {}))
        check(now_schema.get("type") == "integer",
              f"tools/list: now_utc_ms advertised as integer (got {now_schema.get('type')!r})")

        listed = tool_result_payload(client.request(
            "tools/call", {"name": "list_rules", "arguments": {}}))
        check(all("input_schema" in r for r in listed["rules"]),
              "list_rules: every rule carries its input_schema")

        evaluate_args = {"rule_id": "block_extreme",
                         "fields": {"amount": 30000.0},
                         "now_utc_ms": NOW_UTC_MS}
        records = []
        for attempt in (1, 2):
            result = client.request("tools/call", {
                "name": "evaluate_case", "arguments": evaluate_args})
            record = tool_result_payload(result)
            check(not result.get("isError") and "decision_hash" in record
                  and "error_domain" not in record,
                  f"evaluate #{attempt}: decision record returned "
                  f"(hash={str(record.get('decision_hash'))[:16]}...)")
            records.append(record)
        check(records[0] == records[1], "evaluate: two identical calls -> identical records")
        # An int must survive the wire as an int. A typed `now_utc_ms: float`
        # annotation used to turn it into 1700000000000.0, so the same
        # evaluation produced a different record over the wire than in-process.
        check(isinstance(records[0]["now_utc_ms"], int)
              and not isinstance(records[0]["now_utc_ms"], bool),
              f"evaluate: now_utc_ms stays an int "
              f"(got {type(records[0]['now_utc_ms']).__name__})")

        # Every failure below must be isError with a typed error object. Before,
        # these came back as successful calls carrying an error-shaped payload.
        check_error(client, "reserved field",
                    {"rule_id": "allow_small",
                     "fields": {"amount": 1.0, "now_utc_ms": 123},
                     "now_utc_ms": NOW_UTC_MS},
                    "server", 2, "SRV_RESERVED_FIELD", "fields.now_utc_ms")

        # The audit's fail-open, over the wire: amount as a string used to fall
        # through every threshold to the catch-all rule and return a decision.
        check_error(client, "numeric-string field",
                    {"rule_id": "block_extreme", "fields": {"amount": "30000"},
                     "now_utc_ms": NOW_UTC_MS},
                    "server", 6, "SRV_SCHEMA_VIOLATION", "fields.amount")

        # A numeric-string clock used to be silently coerced by the transport.
        check_error(client, "numeric-string clock",
                    {"rule_id": "allow_small", "fields": {"amount": 1.0},
                     "now_utc_ms": str(NOW_UTC_MS)},
                    "engine", 5, "AX_ERR_NOW_UTC_MS_NOT_NUMBER", "now_utc_ms")

        # An undeclared argument used to be dropped without a word.
        check_error(client, "undeclared argument",
                    {"rule_id": "allow_small", "fields": {"amount": 1.0},
                     "now_utc_ms": NOW_UTC_MS, "bogus": 1},
                    "server", 9, "SRV_UNKNOWN_ARGUMENT", "bogus")

        # A 1 MiB field used to produce a ~1.049 MiB response and log line.
        big = client.request("tools/call", {
            "name": "evaluate_case",
            "arguments": {"rule_id": "allow_small",
                          "fields": {"amount": 1.0, "padding": "x" * (1 << 20)},
                          "now_utc_ms": NOW_UTC_MS}})
        big_payload = tool_result_payload(big)
        check(big.get("isError") and big_payload.get("error_code") == 3,
              f"oversized field -> server/3 SRV_FIELDS_TOO_LARGE "
              f"(got {big_payload.get('error_code')})")
        check(len(json.dumps(big)) < 2048,
              f"oversized field: response stays small ({len(json.dumps(big))} bytes)")
    finally:
        client.close()

    lines = decision_log.read_text(encoding="utf-8").splitlines()
    check(len(lines) == 2, f"decision log: exactly 2 lines (got {len(lines)})")
    check(lines[0] == lines[1], "decision log: lines are byte-identical")
    check(json.loads(lines[0])["decision_hash"] == records[0]["decision_hash"],
          "decision log: hash matches the returned record")
    return records[0]["decision_hash"]


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m ruledsl_mcp.smoke",
        description="RuleDSL MCP e2e smoke client")
    parser.add_argument("--engine-lib", required=True,
                        help="path to ruledsl_capi.dll / libruledsl_capi.so")
    parser.add_argument("--rules", default=None,
                        help="rule-library directory (default: the packaged "
                             "example library)")
    parser.add_argument("--wrapper", default=None,
                        help="directory providing the `ruledsl` wrapper "
                             "(only needed when it is not already importable, "
                             "e.g. a bare checkout)")
    args = parser.parse_args(argv)

    try:
        decision_hash = run_smoke(args)
    except SmokeFailure as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr)
        return 1
    print(f"\nPASS  decision_hash={decision_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
