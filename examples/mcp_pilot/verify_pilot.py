#!/usr/bin/env python3
"""Run the purchase-approval pilot against the real MCP stdio server.

The client side is stdlib-only. It reuses RuleDSL's minimal JSON-RPC stdio
client and tool-result decoding primitives; the spawned process is the real
``ruledsl_mcp.server`` with the real engine and committed pilot library.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parent

from ruledsl_mcp import __version__ as SERVER_VERSION  # noqa: E402
from ruledsl_mcp.errors import canonical_json  # noqa: E402
from ruledsl_mcp.smoke import (  # noqa: E402
    JsonRpcStdioClient,
    SmokeFailure,
    call_error,
    tool_result_payload,
)
from ruledsl_mcp.validate import check_schema  # noqa: E402


EXPECTED_TOOLS = ["engine_info", "evaluate_case", "list_rules"]
ACTION_NAMES = {0: "ALLOW", 1: "DECLINE", 2: "REVIEW", 3: "LIMIT"}
MAX_RECEIPT_BYTES = 65536


def check(condition, message):
    if not condition:
        raise SmokeFailure(message)
    print("  ok  " + message)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def call_tool(client, name, arguments):
    result = client.request("tools/call", {"name": name, "arguments": arguments})
    return result, tool_result_payload(result)


def assert_positive(case, record):
    expected = case["expected"]
    decision = record.get("decision", {})
    action_type = decision.get("action_type")
    check(record.get("rule_id") == "purchase_approval",
          "%s: rule id pinned" % case["id"])
    check(decision.get("matched") is True,
          "%s: decision matched" % case["id"])
    check(action_type == expected["action_type"]
          and ACTION_NAMES.get(action_type) == expected["action"],
          "%s: action=%s" % (case["id"], expected["action"]))
    check(decision.get("rule_name") == expected["rule_name"],
          "%s: internal rule=%s" % (case["id"], expected["rule_name"]))
    check(decision.get("outputs") == {
        "reason": expected["reason"], "route": expected["route"]},
        "%s: exact reason/route" % case["id"])
    check(record.get("decision_hash") == expected["decision_hash"],
          "%s: golden decision hash=%s..." %
          (case["id"], expected["decision_hash"][:16]))


def make_receipt(cases, engine_info, listed_rule, records, negative_results,
                 repeat_case, repeat_record):
    positive = []
    for case, record in zip(cases["positive_cases"], records):
        decision = record["decision"]
        positive.append({
            "id": case["id"],
            "action": ACTION_NAMES[decision["action_type"]],
            "rule_name": decision["rule_name"],
            "reason": decision["outputs"]["reason"],
            "route": decision["outputs"]["route"],
            "decision_hash": record["decision_hash"],
        })

    negative = []
    for case, err in zip(cases["negative_cases"], negative_results):
        negative.append({
            "id": case["id"],
            "error_domain": err["error_domain"],
            "error_code": err["error_code"],
            "error_name": err["error_name"],
            "field": err["field"],
            "decision_log_appended": False,
        })

    first_repeat = records[
        [case["id"] for case in cases["positive_cases"]].index(repeat_case)]
    return {
        "receipt_schema": "ruledsl_mcp_pilot_acceptance_v1",
        "scope": "technical_acceptance_only_not_an_audit_ledger_or_system_of_record",
        "limitations": [
            "no whole-record hash or hash chain",
            "no request, principal, tenant, or failure log",
            "no durability, ordering, redaction, or rotation guarantee",
        ],
        "fixed_now_utc_ms": cases["now_utc_ms"],
        "identity": {
            "engine_version": engine_info["engine_version"],
            "abi_level": engine_info["abi_level"],
            "bytecode_schema_version": engine_info["bytecode_schema_version"],
            "decision_record_schema": engine_info["decision_record_schema"],
            "server_version": engine_info["server_version"],
            "manifest_sha256": engine_info["manifest_sha256"],
            "rule_id": listed_rule["rule_id"],
            "rule_version": listed_rule["version"],
            "rule_sha256": listed_rule["rule_sha256"],
            "bytecode_sha256": records[0]["bytecode_sha256"],
        },
        "positive_cases": positive,
        "negative_cases": negative,
        "repeat": {
            "case_id": repeat_case,
            "response_record_byte_identical": (
                canonical_json(first_repeat).encode("utf-8")
                == canonical_json(repeat_record).encode("utf-8")),
            "decision_log_line_byte_identical": True,
            "decision_hash": repeat_record["decision_hash"],
        },
    }


def run(args):
    rules_dir = Path(args.rules).resolve()
    cases_path = Path(args.cases).resolve()
    engine_lib = Path(args.engine_lib).resolve()
    manifest_path = rules_dir / "manifest.json"
    if not engine_lib.is_file():
        raise SmokeFailure("engine library not found: %s" % engine_lib)
    if not manifest_path.is_file():
        raise SmokeFailure("pilot manifest not found: %s" % manifest_path)

    cases = load_json(cases_path)
    manifest = load_json(manifest_path)
    check(cases["rule_id"] == "purchase_approval",
          "acceptance set pins purchase_approval")
    check(sha256_file(manifest_path) == cases["manifest_sha256"],
          "committed manifest hash matches acceptance set")

    env = dict(os.environ)
    pythonpath = []
    if args.wrapper:
        pythonpath.append(str(Path(args.wrapper).resolve()))
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    if pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(pythonpath))
    env["PYTHONUNBUFFERED"] = "1"

    with tempfile.TemporaryDirectory(prefix="ruledsl_mcp_pilot_") as temp_dir:
        decision_log = Path(temp_dir) / "decisions.jsonl"
        cmd = [
            sys.executable, "-m", "ruledsl_mcp.server",
            "--rules", str(rules_dir),
            "--decision-log", str(decision_log),
            "--engine-lib", str(engine_lib),
        ]
        client = JsonRpcStdioClient(cmd, env)
        records = []
        success_responses = []
        negative_results = []
        repeat_record = None
        try:
            initialized = client.request("initialize", {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "ruledsl-mcp-pilot-verifier", "version": "1"},
            })
            server_info = initialized.get("serverInfo", {})
            check(server_info.get("name") == "ruledsl-mcp",
                  "initialize: exact server name")
            check(server_info.get("version") == SERVER_VERSION,
                  "initialize: package server version=%s" % SERVER_VERSION)
            client.notify("notifications/initialized")

            tools = client.request("tools/list").get("tools", [])
            names = sorted(tool["name"] for tool in tools)
            check(names == EXPECTED_TOOLS,
                  "tools/list: exact closed three-tool surface")
            check(all(tool.get("outputSchema") for tool in tools),
                  "tools/list: every tool advertises outputSchema")

            result, listed = call_tool(client, "list_rules", {})
            check(not result.get("isError"), "list_rules succeeds")
            check(len(listed.get("rules", [])) == 1,
                  "list_rules: exactly one manifest-visible rule")
            listed_rule = listed["rules"][0]
            spec = manifest["rules"]["purchase_approval"]
            expected_schema = check_schema(spec["input_schema"], "purchase_approval")
            check(listed_rule == {
                "rule_id": "purchase_approval",
                "version": spec["version"],
                "rule_sha256": cases["rule_sha256"],
                "input_schema": expected_schema,
            }, "list_rules: purchase_approval identity and committed schema")

            result, engine_info = call_tool(client, "engine_info", {})
            check(not result.get("isError"), "engine_info succeeds")
            check(engine_info["manifest_sha256"] == cases["manifest_sha256"],
                  "engine_info: manifest identity matches committed bytes")

            for case in cases["positive_cases"]:
                result, record = call_tool(client, "evaluate_case", {
                    "rule_id": cases["rule_id"],
                    "fields": case["fields"],
                    "now_utc_ms": cases["now_utc_ms"],
                })
                check(not result.get("isError"), "%s: MCP success" % case["id"])
                check(record.get("rule_sha256") == cases["rule_sha256"],
                      "%s: rule source identity" % case["id"])
                assert_positive(case, record)
                records.append(record)
                success_responses.append(result)

            ids = [case["id"] for case in cases["positive_cases"]]
            repeat_index = ids.index(cases["repeat_case"])
            repeat_case = cases["positive_cases"][repeat_index]
            result, repeat_record = call_tool(client, "evaluate_case", {
                "rule_id": cases["rule_id"],
                "fields": repeat_case["fields"],
                "now_utc_ms": cases["now_utc_ms"],
            })
            check(not result.get("isError"), "repeat case: MCP success")
            # JSON-RPC envelope ids differ by design. Compare the complete MCP
            # tool response body and the extracted record, both canonically.
            check(canonical_json(result).encode("utf-8")
                  == canonical_json(success_responses[repeat_index]).encode("utf-8"),
                  "repeat case: MCP tool response bodies are byte-identical")
            check(canonical_json(repeat_record).encode("utf-8")
                  == canonical_json(records[repeat_index]).encode("utf-8"),
                  "repeat case: response records are byte-identical")

            for case in cases["negative_cases"]:
                before = decision_log.read_bytes() if decision_log.exists() else b""
                is_error, err = call_error(client, case["arguments"])
                check(is_error, "%s: isError=true" % case["id"])
                observed = {key: err.get(key) for key in (
                    "error_domain", "error_code", "error_name", "field")}
                check(observed == case["expected_error"],
                      "%s: stable typed error %s/%s field=%s" % (
                          case["id"], err.get("error_domain"),
                          err.get("error_code"), err.get("field")))
                after = decision_log.read_bytes() if decision_log.exists() else b""
                check(after == before, "%s: no decision-log append" % case["id"])
                negative_results.append(err)
        finally:
            client.close()

        expected_records = records + [repeat_record]
        log_lines = decision_log.read_bytes().splitlines()
        check(len(log_lines) == len(expected_records),
              "decision log contains successes only (%d records)" % len(log_lines))
        for index, (line, record) in enumerate(zip(log_lines, expected_records), 1):
            check(line == canonical_json(record).encode("utf-8"),
                  "decision log record %d matches returned record bytes" % index)
        check(log_lines[repeat_index] == log_lines[-1],
              "repeat case: decision-log lines are byte-identical")

        receipt = make_receipt(
            cases, engine_info, listed_rule, records, negative_results,
            cases["repeat_case"], repeat_record)

    if args.receipt:
        receipt_bytes = (canonical_json(receipt) + "\n").encode("utf-8")
        check(len(receipt_bytes) <= MAX_RECEIPT_BYTES,
              "receipt bounded at <= %d bytes (got %d)" %
              (MAX_RECEIPT_BYTES, len(receipt_bytes)))
        receipt_path = Path(args.receipt)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with receipt_path.open("xb") as handle:
            handle.write(receipt_bytes)
        print("  receipt  %s sha256=%s" % (
            receipt_path, hashlib.sha256(receipt_bytes).hexdigest()))

    print("\nPASS  positive=%d negative=%d repeated=1" % (
        len(cases["positive_cases"]), len(cases["negative_cases"])))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify the RuleDSL purchase-approval MCP shadow pilot")
    parser.add_argument("--engine-lib", required=True,
                        help="path to ruledsl_capi.dll / libruledsl_capi.so")
    parser.add_argument("--rules", default=str(PACK_ROOT / "rules"),
                        help="pilot rule library (default: this pack's rules/)")
    parser.add_argument("--cases", default=str(PACK_ROOT / "acceptance_cases.json"),
                        help="machine-readable acceptance cases")
    parser.add_argument("--wrapper", default=None,
                        help="optional directory providing the ruledsl wrapper")
    parser.add_argument("--receipt", default=None,
                        help="optional new file for bounded technical evidence")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (SmokeFailure, KeyError, ValueError, OSError) as exc:
        print("\nFAIL: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
