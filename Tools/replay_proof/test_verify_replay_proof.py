#!/usr/bin/env python3
"""Determinism coverage tests for replay proof verifier mismatch surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


STRICT_FIELDS = (
    "input_hash",
    "options_hash",
    "validation_outcome",
    "validation_code",
)
EMPTY_OPTIONS_HASH = hashlib.sha256(b"{}").hexdigest()


@dataclass(frozen=True)
class Case:
    name: str
    record_a: Path
    record_b: Path
    strict: bool
    expected_exit: int
    expected_field: Optional[str] = None
    expected_invalid_contains: Optional[str] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exercise replay verifier fixtures and optional generated records"
    )
    parser.add_argument("--generated-a", type=Path)
    parser.add_argument("--generated-b", type=Path)
    return parser.parse_args()


def run_case(verifier: Path, case: Case) -> Tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="replay_verify_ext_") as tmp:
        report = Path(tmp) / "report.json"
        cmd = [
            sys.executable,
            str(verifier),
            "--a",
            str(case.record_a),
            "--b",
            str(case.record_b),
            "--out",
            str(report),
        ]
        if case.strict:
            cmd.append("--strict")

        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != case.expected_exit:
            return (
                False,
                f"{case.name}: expected exit {case.expected_exit}, got {proc.returncode}"
                f"\nstdout={proc.stdout}\nstderr={proc.stderr}",
            )

        stdout = proc.stdout
        if case.expected_exit == 0:
            if "PASS: replay proof verified" not in stdout:
                return False, f"{case.name}: expected PASS output; stdout={stdout}"
            if not report.is_file():
                return False, f"{case.name}: expected report.json not produced"
            payload = json.loads(report.read_text(encoding="utf-8"))
            if payload.get("status") != "PASS":
                return False, f"{case.name}: expected report status PASS; got {payload.get('status')}"

        elif case.expected_exit == 2:
            if case.expected_field is None:
                return False, f"{case.name}: expected mismatch field is not configured"
            if f"first_mismatch={case.expected_field}" not in stdout:
                return (
                    False,
                    f"{case.name}: missing expected first_mismatch={case.expected_field}"
                    f"\nstdout={stdout}",
                )
            if not report.is_file():
                return False, f"{case.name}: expected report.json not produced"
            payload = json.loads(report.read_text(encoding="utf-8"))
            mismatches = payload.get("mismatches", {})
            if case.expected_field not in mismatches:
                return (
                    False,
                    f"{case.name}: report mismatches missing field {case.expected_field};"
                    f" got {list(mismatches.keys())}",
                )

        elif case.expected_exit == 1:
            if "INVALID:" not in stdout:
                return False, f"{case.name}: invalid input should print INVALID; stdout={stdout}"
            if case.expected_invalid_contains and case.expected_invalid_contains not in stdout:
                return (
                    False,
                    f"{case.name}: missing expected INVALID fragment '{case.expected_invalid_contains}'"
                    f"\nstdout={stdout}",
                )

    return True, f"{case.name}: ok"


def _write_record(path: Path, record: dict) -> None:
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _different_hash(current: object) -> str:
    zeros = "0" * 64
    return "1" * 64 if current == zeros else zeros


def run_generated_contract(verifier: Path, record_a_path: Path, record_b_path: Path) -> List[str]:
    """Exercise strict parity against records emitted by a real producer run."""
    failures: List[str] = []
    try:
        record_a = json.loads(record_a_path.read_text(encoding="utf-8"))
        record_b = json.loads(record_b_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"generated_records_load: {exc}"]

    for label, record in (("A", record_a), ("B", record_b)):
        if not isinstance(record, dict):
            failures.append(f"generated_{label}: record must be a JSON object")
            continue
        missing = [field for field in STRICT_FIELDS if field not in record]
        if missing:
            failures.append(f"generated_{label}: missing strict fields {missing}")
        if record.get("options_hash") != EMPTY_OPTIONS_HASH:
            failures.append(
                f"generated_{label}: options_hash must pin canonical empty options "
                f"{EMPTY_OPTIONS_HASH}; got {record.get('options_hash')}"
            )
        if record.get("validation_outcome") != "OK":
            failures.append(
                f"generated_{label}: expected validation_outcome=OK; "
                f"got {record.get('validation_outcome')}"
            )
        if record.get("validation_code") != 0:
            failures.append(
                f"generated_{label}: expected validation_code=0; "
                f"got {record.get('validation_code')}"
            )

    if failures:
        return failures

    ok, detail = run_case(
        verifier,
        Case(
            name="generated_real_records_strict_pass",
            record_a=record_a_path,
            record_b=record_b_path,
            strict=True,
            expected_exit=0,
        ),
    )
    print(detail)
    if not ok:
        failures.append(detail)

    mutations = (
        ("engine_version_string", "engine_version_string", "RuleDSL/2.0.0 (abi=1)"),
        ("abi_level", "abi_level", int(record_b["abi_level"]) + 1),
        ("bytecode_hash", "bytecode_hash", _different_hash(record_b.get("bytecode_hash"))),
        ("decision_hash", "effective_result_hash", _different_hash(record_b.get("decision_hash"))),
        ("input_hash", "input_hash", _different_hash(record_b.get("input_hash"))),
        ("options_hash", "options_hash", _different_hash(record_b.get("options_hash"))),
        ("validation_outcome", "validation_outcome", "MUTATED"),
        ("validation_code", "validation_code", int(record_b["validation_code"]) + 1),
    )

    with tempfile.TemporaryDirectory(prefix="replay_generated_mutation_") as tmp:
        tmp_path = Path(tmp)
        for record_field, expected_field, value in mutations:
            mutated = dict(record_b)
            mutated[record_field] = value
            mutated_path = tmp_path / f"mismatch_{record_field}.json"
            _write_record(mutated_path, mutated)
            ok, detail = run_case(
                verifier,
                Case(
                    name=f"generated_mismatch_{record_field}_strict",
                    record_a=record_a_path,
                    record_b=mutated_path,
                    strict=True,
                    expected_exit=2,
                    expected_field=expected_field,
                ),
            )
            print(detail)
            if not ok:
                failures.append(detail)

        for field in STRICT_FIELDS:
            missing = dict(record_b)
            missing.pop(field, None)
            missing_path = tmp_path / f"missing_{field}.json"
            _write_record(missing_path, missing)
            ok, detail = run_case(
                verifier,
                Case(
                    name=f"generated_missing_{field}_strict",
                    record_a=record_a_path,
                    record_b=missing_path,
                    strict=True,
                    expected_exit=1,
                    expected_invalid_contains=f"strict mode requires {field}",
                ),
            )
            print(detail)
            if not ok:
                failures.append(detail)

    return failures


def run_schema_type_guards(verifier: Path, base_record_path: Path) -> List[str]:
    """Pin JSON bool/null traps that Python's type hierarchy otherwise accepts."""
    failures: List[str] = []
    base_record = json.loads(base_record_path.read_text(encoding="utf-8"))
    invalid_values = (
        ("abi_level_bool", "abi_level", True, "abi_level must be string or integer"),
        (
            "bytecode_hash_null",
            "bytecode_hash",
            None,
            "bytecode_hash must be lowercase SHA-256 hex",
        ),
        (
            "validation_code_bool",
            "validation_code",
            True,
            "validation_code must be an integer when present",
        ),
        (
            "error_code_bool",
            "error_code",
            True,
            "error_code must be string or integer when present",
        ),
    )

    with tempfile.TemporaryDirectory(prefix="replay_schema_type_guard_") as tmp:
        tmp_path = Path(tmp)
        for name, field, value, expected in invalid_values:
            invalid = dict(base_record)
            invalid[field] = value
            invalid_path = tmp_path / f"{name}.json"
            _write_record(invalid_path, invalid)
            ok, detail = run_case(
                verifier,
                Case(
                    name=name,
                    record_a=base_record_path,
                    record_b=invalid_path,
                    strict=True,
                    expected_exit=1,
                    expected_invalid_contains=expected,
                ),
            )
            print(detail)
            if not ok:
                failures.append(detail)

    return failures


def main() -> int:
    args = parse_args()
    if (args.generated_a is None) != (args.generated_b is None):
        print("FAIL: --generated-a and --generated-b must be supplied together")
        return 2

    root = Path(__file__).resolve().parent
    verifier = root / "verify_replay_proof.py"

    fixtures = root / "fixtures"
    fixtures_ext = root / "fixtures_extended"
    fixtures_ext_v2 = root / "fixtures_extended_v2"

    base_legacy = fixtures / "pass_a.json"
    base_v2 = fixtures_ext_v2 / "base_v2.json"

    cases: List[Case] = [
        Case(
            name="legacy_pass_non_strict",
            record_a=base_legacy,
            record_b=fixtures / "pass_b.json",
            strict=False,
            expected_exit=0,
        ),
        Case(
            name="legacy_mismatch_decision_non_strict",
            record_a=base_legacy,
            record_b=fixtures / "fail_mismatch_decision.json",
            strict=False,
            expected_exit=2,
            expected_field="effective_result_hash",
        ),
        Case(
            name="legacy_mismatch_engine_non_strict",
            record_a=base_legacy,
            record_b=fixtures_ext / "mismatch_engine_version.json",
            strict=False,
            expected_exit=2,
            expected_field="engine_version_string",
        ),
        Case(
            name="legacy_mismatch_abi_non_strict",
            record_a=base_legacy,
            record_b=fixtures_ext / "mismatch_abi_level.json",
            strict=False,
            expected_exit=2,
            expected_field="abi_level",
        ),
        Case(
            name="legacy_mismatch_bytecode_non_strict",
            record_a=base_legacy,
            record_b=fixtures_ext / "mismatch_bytecode_hash.json",
            strict=False,
            expected_exit=2,
            expected_field="bytecode_hash",
        ),
        Case(
            name="legacy_mismatch_input_non_strict",
            record_a=base_legacy,
            record_b=fixtures_ext / "mismatch_input_hash.json",
            strict=False,
            expected_exit=2,
            expected_field="input_hash",
        ),
        Case(
            name="legacy_schema_missing_field",
            record_a=base_legacy,
            record_b=fixtures_ext / "schema_missing_field.json",
            strict=False,
            expected_exit=1,
        ),
        Case(
            name="strict_missing_new_fields_legacy",
            record_a=base_legacy,
            record_b=fixtures / "pass_b.json",
            strict=True,
            expected_exit=1,
            expected_invalid_contains="strict mode requires options_hash",
        ),
        Case(
            name="v2_mismatch_options_hash_strict",
            record_a=base_v2,
            record_b=fixtures_ext_v2 / "mismatch_options_hash.json",
            strict=True,
            expected_exit=2,
            expected_field="options_hash",
        ),
        Case(
            name="v2_mismatch_validation_outcome_strict",
            record_a=base_v2,
            record_b=fixtures_ext_v2 / "mismatch_validation_outcome.json",
            strict=True,
            expected_exit=2,
            expected_field="validation_outcome",
        ),
        Case(
            name="v2_mismatch_validation_code_strict",
            record_a=base_v2,
            record_b=fixtures_ext_v2 / "mismatch_validation_code.json",
            strict=True,
            expected_exit=2,
            expected_field="validation_code",
        ),
        Case(
            name="v2_strict_missing_options_hash",
            record_a=base_v2,
            record_b=fixtures_ext_v2 / "strict_missing_options_hash.json",
            strict=True,
            expected_exit=1,
            expected_invalid_contains="strict mode requires options_hash",
        ),
        Case(
            name="v2_strict_missing_validation_outcome",
            record_a=base_v2,
            record_b=fixtures_ext_v2 / "strict_missing_validation_outcome.json",
            strict=True,
            expected_exit=1,
            expected_invalid_contains="strict mode requires validation_outcome",
        ),
    ]

    failures: List[str] = []
    for case in cases:
        ok, detail = run_case(verifier=verifier, case=case)
        print(detail)
        if not ok:
            failures.append(detail)

    failures.extend(run_schema_type_guards(verifier=verifier, base_record_path=base_v2))

    if args.generated_a is not None and args.generated_b is not None:
        failures.extend(
            run_generated_contract(
                verifier=verifier,
                record_a_path=args.generated_a,
                record_b_path=args.generated_b,
            )
        )

    if failures:
        print("FAIL: replay verifier extended tests failed")
        return 1

    print("PASS: replay verifier extended tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
