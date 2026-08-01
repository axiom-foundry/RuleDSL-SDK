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
    """Extract the tool's return dict from an MCP tools/call result
    (structuredContent when present, else the first text content block)."""
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        # SDKs wrap bare-dict returns as {"result": ...}; unwrap if so.
        if set(structured) == {"result"}:
            return structured["result"]
        return structured
    for item in result.get("content", []):
        if item.get("type") == "text":
            return json.loads(item["text"])
    raise SmokeFailure(f"tools/call result carries no payload: {result!r}")


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
        names = sorted(t["name"] for t in tools.get("tools", []))
        check(names == EXPECTED_TOOLS,
              f"tools/list: exactly {EXPECTED_TOOLS} (got {names})")

        evaluate_args = {"rule_id": "block_extreme",
                         "fields": {"amount": 30000.0},
                         "now_utc_ms": NOW_UTC_MS}
        records = []
        for attempt in (1, 2):
            result = client.request("tools/call", {
                "name": "evaluate_case", "arguments": evaluate_args})
            record = tool_result_payload(result)
            check("decision_hash" in record and "error_domain" not in record,
                  f"evaluate #{attempt}: decision record returned "
                  f"(hash={str(record.get('decision_hash'))[:16]}...)")
            records.append(record)
        check(records[0] == records[1], "evaluate: two identical calls -> identical records")

        reserved = client.request("tools/call", {
            "name": "evaluate_case",
            "arguments": {"rule_id": "allow_small",
                          "fields": {"amount": 1.0, "now_utc_ms": 123},
                          "now_utc_ms": NOW_UTC_MS}})
        error = tool_result_payload(reserved)
        check(error.get("error_domain") == "server" and error.get("error_code") == 2
              and error.get("error_name") == "SRV_RESERVED_FIELD",
              f"reserved field -> server/2 SRV_RESERVED_FIELD (got {error})")
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
