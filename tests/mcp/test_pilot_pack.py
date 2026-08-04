#!/usr/bin/env python3
"""Engine-free integrity and fail-closed checks for examples/mcp_pilot."""

import ast
import hashlib
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = REPO_ROOT / "examples" / "mcp_pilot"
RULES_ROOT = PACK_ROOT / "rules"
MANIFEST_PATH = RULES_ROOT / "manifest.json"
RULE_PATH = RULES_ROOT / "purchase_approval.ruledsl.txt"
CASES_PATH = PACK_ROOT / "acceptance_cases.json"
VERIFIER_PATH = PACK_ROOT / "verify_pilot.py"

sys.path.insert(0, str(REPO_ROOT / "bindings" / "python"))

from ruledsl_mcp import handlers, validate  # noqa: E402
from ruledsl_mcp.validate import FieldValidationError  # noqa: E402


PILOT_LIMIT_MINOR = 500000
MAX_SAFE_INTEGER = 9007199254740991
REQUIRED_FIELDS = {
    "amount_minor", "currency", "supplier_status",
    "budget_available", "manual_review_required",
}
POSITIVE_IDS = {
    "blocked_supplier_precedence", "usd_requires_review",
    "eur_requires_review", "above_pilot_limit", "budget_unavailable",
    "new_supplier", "manual_review_flag", "exact_threshold_allow",
}
NEGATIVE_IDS = {
    "missing_required_field", "extra_field", "numeric_string_amount",
    "negative_amount", "unsafe_integer_amount", "reserved_clock_field",
    "numeric_string_top_level_clock", "zero_amount",
}

_passed = 0
_failed = 0


def test(name):
    def wrap(fn):
        global _passed, _failed
        try:
            fn()
            _passed += 1
            print("  PASS  " + name)
        except Exception as exc:  # noqa: BLE001 - small standalone runner
            _failed += 1
            print("  FAIL  %s: %s" % (name, exc))
        return fn
    return wrap


def assert_true(value, message="assertion failed"):
    if not value:
        raise AssertionError(message)


def assert_eq(actual, expected, message=""):
    if actual != expected:
        suffix = " (%s)" % message if message else ""
        raise AssertionError("expected %r, got %r%s" % (expected, actual, suffix))


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AssertionError("duplicate JSON key: %r" % key)
        result[key] = value
    return result


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=reject_duplicate_keys,
                      parse_constant=lambda token: (_ for _ in ()).throw(
                          AssertionError("non-standard JSON token: " + token)))


manifest = load_json(MANIFEST_PATH)
cases = load_json(CASES_PATH)
source = RULE_PATH.read_text(encoding="utf-8")
spec = manifest["rules"]["purchase_approval"]
schema = validate.check_schema(spec["input_schema"], "purchase_approval")


@test("manifest v2 exposes exactly purchase_approval")
def _():
    assert_eq(set(manifest), {"manifest_version", "rules"})
    assert_eq(manifest["manifest_version"], 2)
    assert_eq(set(manifest["rules"]), {"purchase_approval"})
    assert_eq(set(spec), {"file", "sha256", "version", "input_schema"})
    assert_eq(spec["file"], RULE_PATH.name)


@test("manifest pins the exact rule bytes and acceptance pins the manifest")
def _():
    rule_hash = hashlib.sha256(RULE_PATH.read_bytes()).hexdigest()
    manifest_hash = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    assert_eq(spec["sha256"], rule_hash)
    assert_eq(cases["rule_sha256"], rule_hash)
    assert_eq(cases["manifest_sha256"], manifest_hash)
    assert_true(re.fullmatch(r"[0-9a-f]{64}", rule_hash) is not None)


@test("input schema is closed, scalar, required, and minor-unit safe")
def _():
    declared = spec["input_schema"]
    assert_eq(declared["type"], "object")
    assert_eq(declared["additionalProperties"], False)
    assert_eq(set(declared["required"]), REQUIRED_FIELDS)
    assert_eq(set(declared["properties"]), REQUIRED_FIELDS)
    assert_eq(declared["properties"]["amount_minor"]["type"], "integer")
    assert_eq(declared["properties"]["amount_minor"]["minimum"], 1)
    assert_eq(declared["properties"]["amount_minor"]["maximum"], MAX_SAFE_INTEGER)
    assert_eq(declared["properties"]["currency"]["enum"], ["TRY", "USD", "EUR"])
    assert_eq(declared["properties"]["supplier_status"]["enum"],
              ["approved", "new", "blocked"])
    assert_true("now_utc_ms" not in declared["properties"])
    for field in REQUIRED_FIELDS:
        types = declared["properties"][field]["type"]
        assert_true(types not in ("object", "array"), field + " must be scalar")


@test("policy ordering is explicit and final action is REVIEW")
def _():
    names = re.findall(r"^rule\s+([a-z_]+)(?:\s+priority\s+(\d+))?\s*\{",
                       source, re.MULTILINE)
    assert_eq([name for name, _priority in names], [
        "decline_blocked_supplier", "review_unsupported_currency",
        "review_above_pilot_limit", "review_no_budget",
        "review_new_supplier", "review_manual_flag",
        "allow_pilot_purchase", "review_fail_closed",
    ])
    assert_eq([int(priority) for _name, priority in names[:-1]],
              [700, 600, 500, 400, 300, 200, 100])
    assert_eq(names[-1][1], "")
    assert_true(re.search(
        r"rule review_fail_closed\s*\{\s*when true;\s*then "
        r"reason = \"fail_closed_fallback\", route = \"human_review\", review;\s*\}",
        source, re.DOTALL) is not None,
        "missing final catch-all REVIEW")
    assert_true("default_allow" not in source)


@test("currency and threshold are enforced explicitly")
def _():
    assert_true('currency != "TRY"' in source)
    assert_true('currency == "TRY"' in source)
    assert_true("amount_minor > %d" % PILOT_LIMIT_MINOR in source)
    assert_true("amount_minor <= %d" % PILOT_LIMIT_MINOR in source)
    assert_true("%d TRY" % PILOT_LIMIT_MINOR not in source,
                "currency metadata is not enforcement")


@test("acceptance cases cover each route and exact amount boundaries")
def _():
    positives = cases["positive_cases"]
    assert_eq({case["id"] for case in positives}, POSITIVE_IDS)
    assert_eq(len(positives), len(POSITIVE_IDS))
    assert_eq(cases["repeat_case"], "exact_threshold_allow")
    by_id = {case["id"]: case for case in positives}
    assert_eq(by_id["exact_threshold_allow"]["fields"]["amount_minor"],
              PILOT_LIMIT_MINOR)
    assert_eq(by_id["exact_threshold_allow"]["expected"]["action"], "ALLOW")
    assert_eq(by_id["above_pilot_limit"]["fields"]["amount_minor"],
              PILOT_LIMIT_MINOR + 1)
    assert_eq(by_id["above_pilot_limit"]["expected"]["action"], "REVIEW")
    assert_eq(by_id["blocked_supplier_precedence"]["expected"]["action"],
              "DECLINE")
    for case in positives:
        assert_eq(set(case["fields"]), REQUIRED_FIELDS, case["id"])
        validate.validate_fields(case["fields"], schema)
        expected = case["expected"]
        assert_true(re.fullmatch(r"[0-9a-f]{64}", expected["decision_hash"]) is not None)
        assert_true(expected["route"] in ("human_review", "procurement_reject",
                                           "straight_through"))


def engine_free_error(arguments):
    shape = handlers.check_call_shape("evaluate_case", arguments)
    if shape is not None:
        return shape
    try:
        validate.validate_now_utc_ms(arguments.get("now_utc_ms"))
        validate.validate_fields(arguments.get("fields"), schema)
    except FieldValidationError as exc:
        return exc.error
    return None


@test("negative corpus pins eight typed fail-closed errors")
def _():
    negatives = cases["negative_cases"]
    assert_eq({case["id"] for case in negatives}, NEGATIVE_IDS)
    assert_eq(len(negatives), len(NEGATIVE_IDS))
    for case in negatives:
        err = engine_free_error(case["arguments"])
        assert_true(err is not None, case["id"] + " was accepted")
        observed = {key: err.get(key) for key in (
            "error_domain", "error_code", "error_name", "field")}
        assert_eq(observed, case["expected_error"], case["id"])


@test("verifier is valid stdlib client code with bounded receipt language")
def _():
    verifier = VERIFIER_PATH.read_text(encoding="utf-8")
    ast.parse(verifier, filename=str(VERIFIER_PATH))
    assert_true("JsonRpcStdioClient" in verifier)
    assert_true("MAX_RECEIPT_BYTES = 65536" in verifier)
    assert_true("technical_acceptance_only_not_an_audit_ledger_or_system_of_record"
                in verifier)
    assert_true("no whole-record hash or hash chain" in verifier)


print("\n%d passed, %d failed" % (_passed, _failed))
sys.exit(1 if _failed else 0)
