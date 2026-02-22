#!/usr/bin/env python3
"""Evidence sanity scanner: blocks environment leakage patterns."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


FORBIDDEN_PATTERNS = [
    ("windows_abs_path", re.compile(r"C:\\\\")),
    ("users_path", re.compile(r"/Users/")),
    ("home_path", re.compile(r"/home/")),
    ("desktop_hostname", re.compile(r"DESKTOP-")),
    ("iso_timestamp", re.compile(r"202[0-9]-[0-9]{2}-[0-9]{2}T")),
]


def collect_targets(paths: list[str]) -> list[Path]:
    if paths:
        targets: list[Path] = []
        for raw in paths:
            p = Path(raw)
            if p.is_file():
                targets.append(p)
            elif p.is_dir():
                targets.extend(sorted(x for x in p.rglob("*") if x.is_file()))
        return sorted(set(targets), key=lambda p: p.as_posix())

    evidence_dir = Path("evidence")
    if evidence_dir.exists() and evidence_dir.is_dir():
        return sorted((x for x in evidence_dir.rglob("*") if x.is_file()), key=lambda p: p.as_posix())

    return [Path("tests/fixtures/evidence_sample.json")]


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    findings: list[tuple[str, int, str]] = []
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        for rule_name, pattern in FORBIDDEN_PATTERNS:
            if pattern.search(line):
                findings.append((rule_name, line_no, line.strip()))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan evidence artifacts for forbidden leakage patterns.")
    parser.add_argument("paths", nargs="*", help="Optional files/directories to scan")
    args = parser.parse_args()

    targets = collect_targets(args.paths)
    targets = sorted(targets, key=lambda p: p.as_posix())

    if not targets:
        print("FAIL evidence-sanity: no files to scan")
        return 1

    all_findings: list[tuple[str, int, str, str]] = []
    for target in targets:
        if not target.exists():
            print(f"FAIL evidence-sanity: missing scan target: {target.as_posix()}")
            return 1
        for rule_name, line_no, line_text in scan_file(target):
            all_findings.append((target.as_posix(), line_no, rule_name, line_text))

    if not all_findings:
        print("PASS evidence-sanity: no forbidden patterns found")
        for target in targets:
            print(f"- scanned {target.as_posix()}")
        return 0

    print(f"FAIL evidence-sanity: {len(all_findings)} forbidden pattern(s) found")
    for file_path, line_no, rule_name, line_text in sorted(all_findings):
        print(f"- {file_path}:{line_no} [{rule_name}] {line_text}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
