#!/usr/bin/env python3
"""Release metadata guard for phase markers, proofing/rc, and stable latest policy."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request


STABLE_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
PROOFING_TAG = re.compile(r"^v\d+\.\d+\.\d+-proofing(?:\.\d+)?$")
RC_TAG = re.compile(r"^v\d+\.\d+\.\d+-rc\.\d+$")
PHASE_MARKER_TAG = re.compile(r"^[a-z0-9-]+-spine-v\d+$")


def load_release_event() -> dict:
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path:
        raise RuntimeError("GITHUB_EVENT_PATH is not set.")
    with open(event_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    release = payload.get("release")
    if not isinstance(release, dict):
        raise RuntimeError("release payload missing from event JSON.")
    return release


def classify_tag(tag: str) -> str:
    if STABLE_TAG.match(tag):
        return "stable"
    if PROOFING_TAG.match(tag):
        return "proofing"
    if RC_TAG.match(tag):
        return "rc"
    if PHASE_MARKER_TAG.match(tag):
        return "phase_marker"
    return "unknown"


def fetch_latest_release(repo: str, token: str) -> dict | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def main() -> int:
    release = load_release_event()
    tag = str(release.get("tag_name", "")).strip()
    prerelease = bool(release.get("prerelease", False))
    release_kind = classify_tag(tag)

    errors: list[str] = []

    if release_kind == "unknown":
        errors.append(
            "Tag naming is invalid. Allowed: stable vX.Y.Z, proofing vX.Y.Z-proofing[.N], rc vX.Y.Z-rc.N, or phase marker <name>-spine-vN."
        )
    elif release_kind in {"proofing", "rc", "phase_marker"} and not prerelease:
        errors.append(f"Tag {tag} is {release_kind} and MUST be prerelease=true.")
    elif release_kind == "stable" and prerelease:
        errors.append(f"Tag {tag} is stable and MUST be prerelease=false.")

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    if repo:
        latest = fetch_latest_release(repo, token)
        if latest is not None:
            latest_tag = str(latest.get("tag_name", "")).strip()
            latest_prerelease = bool(latest.get("prerelease", False))
            if not STABLE_TAG.match(latest_tag):
                errors.append(f"Latest release tag {latest_tag} is not stable semver vX.Y.Z.")
            if latest_prerelease:
                errors.append(f"Latest release {latest_tag} MUST NOT be prerelease.")

    if errors:
        print("FAIL release-guard")
        for item in errors:
            print(f"- {item}")
        return 1

    print("PASS release-guard")
    print(f"- tag: {tag}")
    print(f"- kind: {release_kind}")
    print(f"- prerelease: {str(prerelease).lower()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pylint: disable=broad-except
        print("FAIL release-guard")
        print(f"- error: {exc}")
        raise SystemExit(1)
