#!/usr/bin/env python3
"""Self-test for the non-goal claim linter: precision (pass fixture + real surface) + recall (fail fixture)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINT = HERE / "check_non_goal_claims.py"
REPO = HERE.parent.parent  # RuleDSL-SDK root


def run(*paths: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(LINT), *paths],
        capture_output=True, text=True, cwd=str(REPO),
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    failures: list[str] = []

    # 1) Pass fixture -> clean (exit 0, no findings).
    rc, out = run("Tools/doc_policy_lint/fixtures/pass_non_goal_ok.md")
    if rc != 0:
        failures.append(f"pass fixture should be clean but lint failed:\n{out}")

    # 2) Fail fixture -> flagged (exit 1) and catches all 5 affirmative overclaims.
    rc, out = run("Tools/doc_policy_lint/fixtures/fail_overclaim.md")
    found = out.count("fail_overclaim.md:")
    if rc == 0:
        failures.append(f"fail fixture should be flagged but lint passed:\n{out}")
    elif found < 5:
        failures.append(f"fail fixture: expected 5 flagged lines, got {found}:\n{out}")

    # 3) Real public surface -> clean (no false positives on the honest docs).
    rc, out = run("--allow-missing")
    if rc != 0:
        failures.append(f"real public surface produced findings (false positives?):\n{out}")

    if failures:
        print("DOC-POLICY SELF-TEST FAILED")
        for f in failures:
            print("---"); print(f)
        return 1
    print("DOC-POLICY SELF-TEST PASSED (precision: pass fixture + real surface clean; recall: 5/5 overclaims caught)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
