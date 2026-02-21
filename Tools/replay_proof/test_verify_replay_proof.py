#!/usr/bin/env python3
"""Determinism coverage tests for replay proof verifier mismatch surfaces."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Case:
    name: str
    record_a: Path
    record_b: Path
    strict: bool
    expected_exit: int
    expected_field: Optional[str] = None
    expected_invalid_contains: Optional[str] = None


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


def main() -> int:
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

    if failures:
        print("FAIL: replay verifier extended tests failed")
        return 1

    print("PASS: replay verifier extended tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
