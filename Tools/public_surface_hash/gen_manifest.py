#!/usr/bin/env python3
"""Generate/check deterministic hash manifest for public surface headers."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INCLUDE_ROOT = REPO_ROOT / "include"
DEFAULT_MANIFEST = REPO_ROOT / "docs" / "governance" / "public_surface_manifest.sha256"


def canonical_bytes(path: Path) -> bytes:
    # Normalize CRLF/LF to avoid platform checkout drift in manifest hashes.
    return path.read_bytes().replace(b"\r\n", b"\n")


def enumerate_public_headers() -> list[Path]:
    if not INCLUDE_ROOT.exists():
        return []
    files = [p for p in INCLUDE_ROOT.rglob("*") if p.is_file()]
    return sorted(files, key=lambda p: p.relative_to(REPO_ROOT).as_posix())


def build_manifest_text(files: list[Path]) -> str:
    lines: list[str] = []
    for file_path in files:
        relative = file_path.relative_to(REPO_ROOT).as_posix()
        digest = hashlib.sha256(canonical_bytes(file_path)).hexdigest()
        lines.append(f"{digest}  {relative}")
    return "\n".join(lines) + "\n"


def resolve_manifest_path(raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def run_check(manifest_path: Path, generated_text: str) -> int:
    if not manifest_path.exists():
        print(f"FAIL public-surface: manifest missing: {manifest_path}")
        print("Regenerate with: python Tools/public_surface_hash/gen_manifest.py")
        return 1

    expected_text = manifest_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if expected_text == generated_text:
        print("PASS public-surface: manifest matches committed public surface inventory.")
        return 0

    print("FAIL public-surface: committed manifest is out of date.")
    print("Regenerate with: python Tools/public_surface_hash/gen_manifest.py")
    print('If contract-critical files changed, PR body MUST include: "Contract change: YES"')

    diff = difflib.unified_diff(
        expected_text.splitlines(),
        generated_text.splitlines(),
        fromfile="committed",
        tofile="generated",
        lineterm="",
    )
    for line in list(diff)[:40]:
        print(line)
    return 1


def run_write(manifest_path: Path, generated_text: str, file_count: int) -> int:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(generated_text, encoding="utf-8", newline="\n")
    rel = manifest_path.relative_to(REPO_ROOT).as_posix() if manifest_path.is_relative_to(REPO_ROOT) else str(manifest_path)
    print(f"Wrote {rel} with {file_count} file entries.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate/check public include hash manifest.")
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST.relative_to(REPO_ROOT)),
        help="Manifest path (default: docs/governance/public_surface_manifest.sha256)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check committed manifest against generated inventory and fail on drift.",
    )
    args = parser.parse_args()

    files = enumerate_public_headers()
    if not files:
        print("FAIL public-surface: no files found under include/.")
        return 1

    generated_text = build_manifest_text(files)
    manifest_path = resolve_manifest_path(args.manifest)

    if args.check:
        return run_check(manifest_path, generated_text)

    return run_write(manifest_path, generated_text, len(files))


if __name__ == "__main__":
    sys.exit(main())
