#!/usr/bin/env python3
"""Determinism coverage tests for replay proof verifier mismatch surfaces."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple


Case = Tuple[str, int, Optional[str]]


def run_case(
    verifier: Path,
    baseline: Path,
    candidate: Path,
    expected_exit: int,
    expected_field: Optional[str],
) -> Tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="replay_verify_ext_") as tmp:
        report = Path(tmp) / "report.json"
        cmd = [
            sys.executable,
            str(verifier),
            "--a",
            str(baseline),
            "--b",
            str(candidate),
            "--out",
            str(report),
            "--strict",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != expected_exit:
            return (
                False,
                f"{candidate.name}: expected exit {expected_exit}, got {proc.returncode}\n"
                f"stdout={proc.stdout}\nstderr={proc.stderr}",
            )

        stdout = proc.stdout
        if expected_exit == 2:
            if expected_field is None:
                return False, f"{candidate.name}: expected mismatch field is not configured"
            if f"first_mismatch={expected_field}" not in stdout:
                return (
                    False,
                    f"{candidate.name}: missing expected first_mismatch={expected_field}\nstdout={stdout}",
                )
            if not report.is_file():
                return False, f"{candidate.name}: expected report.json not produced"
            payload = json.loads(report.read_text(encoding="utf-8"))
            mismatches = payload.get("mismatches", {})
            if expected_field not in mismatches:
                return (
                    False,
                    f"{candidate.name}: report mismatches missing field {expected_field}; got {list(mismatches.keys())}",
                )
        elif expected_exit == 1:
            if "INVALID:" not in stdout:
                return False, f"{candidate.name}: invalid input should print INVALID; stdout={stdout}"

    return True, f"{candidate.name}: ok"


def main() -> int:
    root = Path(__file__).resolve().parent
    verifier = root / "verify_replay_proof.py"
    baseline = root / "fixtures" / "pass_a.json"
    fixtures_ext = root / "fixtures_extended"

    cases: List[Case] = [
        ("mismatch_engine_version.json", 2, "engine_version_string"),
        ("mismatch_abi_level.json", 2, "abi_level"),
        ("mismatch_bytecode_hash.json", 2, "bytecode_hash"),
        ("mismatch_input_hash.json", 2, "input_hash"),
        ("schema_missing_field.json", 1, None),
    ]

    failures: List[str] = []
    for name, expected_exit, expected_field in cases:
        ok, detail = run_case(
            verifier=verifier,
            baseline=baseline,
            candidate=fixtures_ext / name,
            expected_exit=expected_exit,
            expected_field=expected_field,
        )
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
