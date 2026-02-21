#!/usr/bin/env python3
"""Verify replay proof equality between two decision records."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCHEMA_VERSION = "replay_proof_v1"
REPORT_SCHEMA_VERSION = "replay_proof_report_v1"
HASH_FIELDS = {"bytecode_hash", "decision_hash", "result_hash", "input_hash", "options_hash"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify replay proof between two decision records")
    parser.add_argument("--a", required=True, type=Path, help="Record A JSON path")
    parser.add_argument("--b", required=True, type=Path, help="Record B JSON path")
    parser.add_argument("--out", type=Path, default=None, help="Optional output report JSON path")
    parser.add_argument("--strict", action="store_true", help="Require strict parity for replay equality surface")
    return parser.parse_args()


def is_sha256_hex(value: str) -> bool:
    if len(value) != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in value)


def load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"record must be a JSON object: {path}")
    return payload


def get_effective_result_hash(record: Dict[str, Any], label: str) -> str:
    decision_hash = record.get("decision_hash")
    result_hash = record.get("result_hash")
    if decision_hash is None and result_hash is None:
        raise ValueError(f"{label}: record must provide decision_hash or result_hash")
    if decision_hash is not None:
        if not isinstance(decision_hash, str):
            raise ValueError(f"{label}: decision_hash must be a string")
        return decision_hash.lower()
    if not isinstance(result_hash, str):
        raise ValueError(f"{label}: result_hash must be a string")
    return result_hash.lower()


def validate_record(record: Dict[str, Any], label: str) -> Dict[str, Any]:
    required = ["schema_version", "engine_version_string", "abi_level", "bytecode_hash"]
    for key in required:
        if key not in record:
            raise ValueError(f"{label}: missing required field '{key}'")

    schema_version = record.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"{label}: schema_version must be '{SCHEMA_VERSION}'")

    engine = record.get("engine_version_string")
    if not isinstance(engine, str) or not engine.strip():
        raise ValueError(f"{label}: engine_version_string must be a non-empty string")

    abi_level = record.get("abi_level")
    if not isinstance(abi_level, (str, int)):
        raise ValueError(f"{label}: abi_level must be string or integer")

    for key in HASH_FIELDS:
        if key in record and record[key] is not None:
            val = record[key]
            if not isinstance(val, str) or not is_sha256_hex(val.lower()):
                raise ValueError(f"{label}: {key} must be lowercase SHA-256 hex")

    if "validation_outcome" in record and record["validation_outcome"] is not None:
        validation_outcome = record["validation_outcome"]
        if not isinstance(validation_outcome, str) or not validation_outcome.strip():
            raise ValueError(f"{label}: validation_outcome must be a non-empty string when present")

    if "validation_code" in record and record["validation_code"] is not None:
        validation_code = record["validation_code"]
        if not isinstance(validation_code, int):
            raise ValueError(f"{label}: validation_code must be an integer when present")

    if "input_descriptor" in record and record["input_descriptor"] is not None and not isinstance(record["input_descriptor"], str):
        raise ValueError(f"{label}: input_descriptor must be string when present")

    if "error_code" in record and record["error_code"] is not None and not isinstance(record["error_code"], (str, int)):
        raise ValueError(f"{label}: error_code must be string or integer when present")

    for key in ["error_message", "notes", "timestamp_utc"]:
        if key in record and record[key] is not None and not isinstance(record[key], str):
            raise ValueError(f"{label}: {key} must be string when present")

    normalized: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "engine_version_string": engine,
        "abi_level": str(abi_level),
        "bytecode_hash": str(record["bytecode_hash"]).lower(),
        "effective_result_hash": get_effective_result_hash(record, label),
        "input_hash": str(record["input_hash"]).lower() if record.get("input_hash") is not None else None,
        "options_hash": str(record["options_hash"]).lower() if record.get("options_hash") is not None else None,
        "validation_outcome": record.get("validation_outcome"),
        "validation_code": record.get("validation_code"),
        "error_code": str(record["error_code"]) if record.get("error_code") is not None else None,
    }
    return normalized


def ensure_strict_fields(a: Dict[str, Any], b: Dict[str, Any]) -> None:
    required = ["input_hash", "options_hash", "validation_outcome", "validation_code"]
    for field in required:
        if a.get(field) is None or b.get(field) is None:
            raise ValueError(f"strict mode requires {field} in both records")


def compute_proof_hash(compared_fields: Dict[str, Dict[str, Any]]) -> str:
    lines: List[str] = []
    for field in sorted(compared_fields.keys()):
        value_a = compared_fields[field]["a"]
        value_b = compared_fields[field]["b"]
        lines.append(f"{field}.a={value_a}")
        lines.append(f"{field}.b={value_b}")
    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compare_records(
    a: Dict[str, Any],
    b: Dict[str, Any],
    strict: bool,
) -> Tuple[bool, Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], List[str]]:
    compared: Dict[str, Dict[str, Any]] = {}
    mismatches: Dict[str, Dict[str, Any]] = {}
    notes: List[str] = []

    base_fields = [
        "engine_version_string",
        "abi_level",
        "bytecode_hash",
        "effective_result_hash",
    ]
    for field in base_fields:
        compared[field] = {"a": a[field], "b": b[field]}

    def maybe_compare(field: str) -> None:
        a_val = a.get(field)
        b_val = b.get(field)
        if strict:
            compared[field] = {"a": a_val, "b": b_val}
            return

        if a_val is not None and b_val is not None:
            compared[field] = {"a": a_val, "b": b_val}
        else:
            notes.append(f"{field} comparison skipped (missing on one or both records)")

    maybe_compare("input_hash")
    maybe_compare("options_hash")
    maybe_compare("validation_outcome")
    maybe_compare("validation_code")

    if a.get("error_code") is not None and b.get("error_code") is not None:
        compared["error_code"] = {"a": a["error_code"], "b": b["error_code"]}
    elif strict and (a.get("error_code") is not None or b.get("error_code") is not None):
        compared["error_code"] = {"a": a.get("error_code"), "b": b.get("error_code")}
        notes.append("strict mode requires symmetric error_code presence")

    for field, values in compared.items():
        if values["a"] != values["b"]:
            mismatches[field] = values

    return len(mismatches) == 0, compared, mismatches, notes


def write_report(path: Path, report: Dict[str, Any]) -> None:
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")


def main() -> int:
    args = parse_args()
    try:
        a_raw = load_json(args.a)
        b_raw = load_json(args.b)
        a_norm = validate_record(a_raw, "A")
        b_norm = validate_record(b_raw, "B")
        if args.strict:
            ensure_strict_fields(a_norm, b_norm)
    except ValueError as exc:
        print(f"INVALID: {exc}")
        return 1

    matched, compared, mismatches, notes = compare_records(a_norm, b_norm, args.strict)
    proof_hash = compute_proof_hash(compared)

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "PASS" if matched else "FAIL",
        "strict": bool(args.strict),
        "record_a": str(args.a),
        "record_b": str(args.b),
        "compared_fields": compared,
        "mismatches": mismatches,
        "proof_hash": proof_hash,
        "notes": notes,
    }

    if args.out is not None:
        write_report(args.out, report)

    if matched:
        print(f"PASS: replay proof verified (proof_hash={proof_hash})")
        return 0

    first_field = sorted(mismatches.keys())[0]
    first_vals = mismatches[first_field]
    print("FAIL: replay proof mismatch")
    print(f"  first_mismatch={first_field}")
    print(f"  a={first_vals.get('a')}")
    print(f"  b={first_vals.get('b')}")
    print(f"  proof_hash={proof_hash}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
