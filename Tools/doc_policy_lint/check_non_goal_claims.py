#!/usr/bin/env python3
"""Non-goal claim linter: blocks affirmative public claims of RFC-001 non-goal capabilities.

RFC-001 (system boundary) declares hard non-goals: RuleDSL MUST NOT be presented as a
transport/API-gateway/network layer, a persistence/workflow/scheduling/orchestration system,
or a distributed-consensus/multi-node coordination system. The public surface (contract docs,
governance RFCs, architecture docs, and the marketing site) is the recurring place such an
overclaim could creep in and damage credibility. This lint institutionalizes the boundary so
future drift is caught automatically.

Design (precision over recall, so the legitimate non-goal prose passes cleanly):
- A line is flagged only when RuleDSL (or the engine/SDK/compiler/library/runtime) is the
  SUBJECT, an AFFIRMATIVE capability verb follows, and a non-goal capability term follows that
  — in order, within one sentence — AND the sentence carries no negation/non-goal/host-scope
  marker. So "RuleDSL MUST NOT be interpreted as a network protocol" and "Host SHALL manage
  transport, persistence" both pass; "RuleDSL is a workflow orchestration engine" fails.

Exit: 0 = clean (PASS), 1 = at least one affirmative non-goal claim (FAIL) or a missing target.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Default public-surface target set (relative to repo root). Kept here so CI can call with no args.
DEFAULT_TARGETS = [
    "docs/contracts",
    "docs/architecture",
    "docs/governance/rfc_001_system_boundary_v1.md",
    "docs/governance/rfc_001_test_matrix_v1.md",
    "site/index.html",
]

# Non-goal capability terms, grouped by RFC-001 family. Matched case-insensitively.
DENY_FAMILIES: dict[str, list[str]] = {
    "network_transport": [
        r"network protocol", r"transport layer", r"transport protocol", r"api gateway",
        r"message queue", r"message broker", r"wire protocol", r"rpc framework",
        r"networking stack", r"http server", r"web server",
    ],
    "persistence_workflow": [
        r"persistence layer", r"persistence system", r"database( engine| system)?",
        r"datastore", r"data store", r"storage engine", r"workflow engine",
        r"workflow system", r"workflow orchestrat\w*", r"scheduler", r"scheduling system",
        r"job queue", r"orchestration( engine| system)?", r"orchestrator",
    ],
    "consensus_cluster": [
        r"distributed consensus", r"consensus protocol", r"consensus algorithm",
        r"multi-node coordination", r"cluster coordination", r"state coordination",
        r"state replication", r"leader election", r"quorum",
    ],
}

# Conservative subject set: only RuleDSL-itself referents (bare "it"/"this" excluded as ambiguous).
SUBJECT = r"(?:RuleDSL|the (?:rule )?engine|the SDK|the compiler|the library|the runtime|the product)"
# Affirmative capability verbs (a positive claim of being / providing the capability).
AFFIRM = (
    r"(?:is|are|provides?|offers?|includes?|acts? as|serves? as|implements?|supports?|handles?|"
    r"manages?|performs?|features?|delivers?|enables?|ships? with|comes with|functions? as|"
    r"works? as|doubles? as|can be used as|operates? as)"
)
# Negation / non-goal / host-scope markers that make a sentence safe (it is denying or out-of-scope).
NEGATION = re.compile(
    r"\b(?:not|never|no|cannot|can't|without|out of scope|non-goal|isn't|aren't|wasn't|don't|"
    r"doesn't|must not|excludes?|neither|nor|remain(?:s)?|responsibilit|assumes no|n't)\b",
    re.IGNORECASE,
)

_TERMS_RE = re.compile("|".join(t for terms in DENY_FAMILIES.values() for t in terms), re.IGNORECASE)
_FAMILY_RES = {fam: re.compile("|".join(terms), re.IGNORECASE) for fam, terms in DENY_FAMILIES.items()}
_CLAIM_RE = re.compile(rf"{SUBJECT}\b.{{0,60}}?\b{AFFIRM}\b.{{0,40}}?(?:{_TERMS_RE.pattern})", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n")


def _family_of(text: str) -> str:
    for fam, rx in _FAMILY_RES.items():
        if rx.search(text):
            return fam
    return "unknown"


def scan_text(text: str, is_html: bool) -> list[tuple[int, str, str]]:
    """Return (line_no, family, sentence) for each affirmative non-goal claim."""
    findings: list[tuple[int, str, str]] = []
    lines = text.splitlines()
    for line_no, raw in enumerate(lines, start=1):
        line = _TAG_RE.sub(" ", raw) if is_html else raw
        if not _TERMS_RE.search(line):
            continue
        for sent in _SENT_SPLIT.split(line):
            if not _TERMS_RE.search(sent):
                continue
            if NEGATION.search(sent):
                continue  # denial / non-goal / host-scope -> safe
            if _CLAIM_RE.search(sent):
                findings.append((line_no, _family_of(sent), sent.strip()[:200]))
    return findings


def collect_targets(paths: list[str]) -> list[Path]:
    raw = paths if paths else DEFAULT_TARGETS
    targets: list[Path] = []
    for r in raw:
        p = Path(r)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            targets.extend(x for x in p.rglob("*") if x.is_file() and x.suffix in {".md", ".html", ".txt"})
    return sorted(set(targets), key=lambda p: p.as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint public surface for affirmative RFC-001 non-goal claims.")
    parser.add_argument("paths", nargs="*", help="Files/dirs to scan (default: public contract+site set)")
    parser.add_argument("--allow-missing", action="store_true", help="Skip (not fail) missing default targets")
    args = parser.parse_args()

    targets = collect_targets(args.paths)
    if not targets:
        print("FAIL doc-policy: no files to scan")
        return 1

    all_findings: list[tuple[str, int, str, str]] = []
    for t in targets:
        if not t.exists():
            if args.allow_missing and not args.paths:
                continue
            print(f"FAIL doc-policy: missing scan target: {t.as_posix()}")
            return 1
        for line_no, family, sent in scan_text(t.read_text(encoding="utf-8"), t.suffix == ".html"):
            all_findings.append((t.as_posix(), line_no, family, sent))

    if not all_findings:
        print("PASS doc-policy: no affirmative non-goal claims found")
        for t in targets:
            print(f"- scanned {t.as_posix()}")
        return 0

    print(f"FAIL doc-policy: {len(all_findings)} affirmative non-goal claim(s) found")
    for file_path, line_no, family, sent in sorted(all_findings):
        print(f"- {file_path}:{line_no} [{family}] {sent}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
