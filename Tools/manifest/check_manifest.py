#!/usr/bin/env python3
"""MANIFEST.txt regenerator + parity gate.

MANIFEST.txt is the authoritative inventory of the published SDK surface. It silently drifted
(listed ~33 files while the tree had ~130), so a stale claim of "authoritative inventory" went
unchecked. This tool regenerates it from the actual tracked tree and, with --check, fails CI if
MANIFEST and the tree disagree — so the inventory can never silently drift again.

Surface = every git-tracked file EXCEPT internal tooling/CI (Tools/, .github/, reports/). Everything
else (docs, examples, include, bindings, site, tests, root files) is customer-facing and listed.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

MANIFEST = "MANIFEST.txt"
EXCLUDE_PREFIXES = ("Tools/", ".github/", "reports/")
HEADER = [
    "# RuleDSL SDK Public Manifest",
    "# Purpose: Inventory of files intentionally published in this repository.",
    "# Paths are repository-root-relative. Excludes internal tooling/CI (Tools/, .github/, reports/).",
    "# Generated + checked by Tools/manifest/check_manifest.py — do not edit by hand.",
    "",
]


def tracked_surface() -> list[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    files = [ln for ln in out.splitlines() if ln and not ln.startswith(EXCLUDE_PREFIXES)]
    return sorted(files)


def manifest_listed(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(
        ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    )


def render(files: list[str]) -> str:
    return "\n".join(HEADER + files) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate or check MANIFEST.txt against the tracked tree.")
    ap.add_argument("--check", action="store_true", help="Fail if MANIFEST disagrees with the tree.")
    args = ap.parse_args()

    surface = tracked_surface()
    path = Path(MANIFEST)

    if not args.check:
        path.write_text(render(surface), encoding="utf-8")
        print(f"Wrote {MANIFEST} with {len(surface)} entries.")
        return 0

    listed = manifest_listed(path)
    listed_set, surface_set = set(listed), set(surface)
    missing = sorted(surface_set - listed_set)   # in tree, not in MANIFEST
    extra = sorted(listed_set - surface_set)      # in MANIFEST, not in tree
    if not missing and not extra:
        print(f"PASS manifest: MANIFEST.txt matches the tracked surface ({len(surface)} files).")
        return 0
    print(f"FAIL manifest: MANIFEST.txt is out of date ({len(missing)} missing, {len(extra)} stale).")
    for m in missing:
        print(f"  - MISSING (in tree, not listed): {m}")
    for e in extra:
        print(f"  - STALE (listed, not in tree): {e}")
    print("\nRegenerate with: python Tools/manifest/check_manifest.py")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
