"""RuleDSL MCP rule-library loader tests (Phase 1).

Covers: happy path (load + get + compile + bytecode_sha256), fatal paths
(unknown/missing manifest_version, sha256 mismatch, missing file, escape),
manifest-only visibility, unknown rule_id, and load-to-load determinism.

Requires the engine DLL and the public SDK python wrapper:
  RULEDSL_DLL      (default: <repo>/build/Release/ruledsl_capi.dll)
  RULEDSL_WRAPPER  (default: <repo>/../RuleDSL-SDK/bindings/python)
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

sys.path.insert(0, str(REPO_ROOT / "bindings" / "python"))
from ruledsl_mcp import (  # noqa: E402
    LibraryError,
    ManifestVersionError,
    RuleHashMismatchError,
    UnknownRuleIdError,
    load_library,
)

DLL_PATH = os.environ.get(
    "RULEDSL_DLL", str(REPO_ROOT / "build" / "Release" / "ruledsl_capi.dll"))
WRAPPER_DIR = os.environ.get(
    "RULEDSL_WRAPPER", str(REPO_ROOT.parent / "RuleDSL-SDK" / "bindings" / "python"))
sys.path.insert(0, WRAPPER_DIR)
from ruledsl import RuleDSL  # noqa: E402

RULES_DIR = REPO_ROOT / "rules"

# ---------------------------------------------------------------------------
# Test infrastructure (same harness style as Tests/bindings)
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0
_errors = []


def test(name):
    def decorator(fn):
        global _passed, _failed
        try:
            fn()
            _passed += 1
            print(f"  PASS  {name}")
        except Exception as e:
            _failed += 1
            _errors.append((name, e))
            print(f"  FAIL  {name}: {e}")
        return fn
    return decorator


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(msg or "condition is false")


def assert_eq(a, b, msg=""):
    if a != b:
        raise AssertionError(f"Expected {b!r}, got {a!r}" + (f" ({msg})" if msg else ""))


def assert_raises(exc_type, fn, contains=()):
    try:
        fn()
    except exc_type as e:
        for fragment in contains:
            if fragment not in str(e):
                raise AssertionError(f"{exc_type.__name__} message missing {fragment!r}: {e}")
        return e
    raise AssertionError(f"{exc_type.__name__} not raised")


def write_fixture_library(root, rules, manifest_version=1, tamper_sha=None,
                          extra_files=(), omit_version=False):
    """Write a temp library. rules: {rule_id: source}. Returns library dir."""
    root = Path(root)
    manifest = {} if omit_version else {"manifest_version": manifest_version}
    manifest["rules"] = {}
    for rule_id, source in rules.items():
        fname = f"{rule_id}.ruledsl.txt"
        data = source.encode("utf-8")
        (root / fname).write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        if tamper_sha == rule_id:
            sha = "0" * 64
        manifest["rules"][rule_id] = {"file": fname, "sha256": sha, "version": "1.0.0"}
    for fname, source in extra_files:
        (root / fname).write_bytes(source.encode("utf-8"))
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


VALID_RULE = 'rule r1 { when amount > 1000; then decline; }'

engine = RuleDSL(DLL_PATH)

# ---------------------------------------------------------------------------
# Happy path — committed rules/ library
# ---------------------------------------------------------------------------

@test("happy: committed rules/ library loads, verifies, compiles")
def _():
    lib = load_library(RULES_DIR, compiler=engine)
    assert_eq(lib.rule_ids(), ["allow_small", "block_extreme", "velocity_limits"])
    entry = lib.get("velocity_limits")
    assert_true("block_extreme" in entry.source, "source content")
    assert_eq(entry.version, "1.0.0")
    for rule_id in lib.rule_ids():
        e = lib.get(rule_id)
        assert_true(e.bytecode and len(e.bytecode) > 0, f"{rule_id}: empty bytecode")
        assert_true(len(e.bytecode_sha256) == 64
                    and all(c in "0123456789abcdef" for c in e.bytecode_sha256),
                    f"{rule_id}: bytecode_sha256 not 64-hex")
        assert_eq(e.rule_sha256, hashlib.sha256(e.source.encode()).hexdigest(),
                  f"{rule_id}: rule_sha256")


@test("happy: manifest_sha256 matches the manifest file bytes")
def _():
    lib = load_library(RULES_DIR)
    expected = hashlib.sha256((RULES_DIR / "manifest.json").read_bytes()).hexdigest()
    assert_eq(lib.manifest_sha256, expected)


@test("happy: load without compiler leaves bytecode fields None")
def _():
    lib = load_library(RULES_DIR)
    e = lib.get("allow_small")
    assert_true(e.bytecode is None and e.bytecode_sha256 is None)


# ---------------------------------------------------------------------------
# Fatal paths — all must refuse to serve anything
# ---------------------------------------------------------------------------

@test("fatal: unknown manifest_version")
def _():
    with tempfile.TemporaryDirectory() as td:
        root = write_fixture_library(td, {"r1": VALID_RULE}, manifest_version=99)
        assert_raises(ManifestVersionError, lambda: load_library(root), contains=["99"])


@test("fatal: missing manifest_version")
def _():
    with tempfile.TemporaryDirectory() as td:
        root = write_fixture_library(td, {"r1": VALID_RULE}, omit_version=True)
        assert_raises(ManifestVersionError, lambda: load_library(root),
                      contains=["manifest_version missing"])


@test("fatal: sha256 mismatch names rule_id + expected + found")
def _():
    with tempfile.TemporaryDirectory() as td:
        root = write_fixture_library(td, {"r1": VALID_RULE, "r2": VALID_RULE},
                                     tamper_sha="r2")
        real = hashlib.sha256(VALID_RULE.encode()).hexdigest()
        assert_raises(RuleHashMismatchError, lambda: load_library(root),
                      contains=["'r2'", "0" * 64, real])


@test("fatal: manifest references missing file")
def _():
    with tempfile.TemporaryDirectory() as td:
        root = write_fixture_library(td, {"r1": VALID_RULE})
        (root / "r1.ruledsl.txt").unlink()
        assert_raises(LibraryError, lambda: load_library(root), contains=["not found"])


@test("fatal: manifest file escaping the library directory")
def _():
    with tempfile.TemporaryDirectory() as td:
        outside = Path(td) / "outside.ruledsl.txt"
        outside.write_bytes(VALID_RULE.encode())
        libdir = Path(td) / "lib"
        libdir.mkdir()
        sha = hashlib.sha256(VALID_RULE.encode()).hexdigest()
        (libdir / "manifest.json").write_text(json.dumps({
            "manifest_version": 1,
            "rules": {"r1": {"file": "../outside.ruledsl.txt",
                             "sha256": sha, "version": "1.0.0"}},
        }), encoding="utf-8")
        assert_raises(LibraryError, lambda: load_library(libdir), contains=["escapes"])


@test("fatal: missing manifest.json")
def _():
    with tempfile.TemporaryDirectory() as td:
        assert_raises(LibraryError, lambda: load_library(td), contains=["manifest not found"])


@test("fatal: compile failure is fatal at load")
def _():
    with tempfile.TemporaryDirectory() as td:
        root = write_fixture_library(td, {"bad": "rule { this is not valid"})
        assert_raises(LibraryError, lambda: load_library(root, compiler=engine),
                      contains=["'bad'", "compile failed"])


# ---------------------------------------------------------------------------
# Visibility + unknown rule_id
# ---------------------------------------------------------------------------

@test("manifest-only visibility: on-disk file not in manifest is invisible")
def _():
    with tempfile.TemporaryDirectory() as td:
        root = write_fixture_library(td, {"r1": VALID_RULE},
                                     extra_files=[("ghost.ruledsl.txt", VALID_RULE)])
        lib = load_library(root)
        assert_eq(lib.rule_ids(), ["r1"])
        assert_true("ghost" not in lib)
        assert_raises(UnknownRuleIdError, lambda: lib.get("ghost"))


@test("unknown rule_id: SRV_UNKNOWN_RULE_ID semantics (code=1)")
def _():
    lib = load_library(RULES_DIR)
    e = assert_raises(UnknownRuleIdError, lambda: lib.get("no_such_rule"),
                      contains=["no_such_rule"])
    assert_eq(e.server_error_code, 1)
    assert_eq(e.server_error_name, "SRV_UNKNOWN_RULE_ID")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

@test("determinism: two independent loads yield identical bytecode_sha256")
def _():
    first = load_library(RULES_DIR, compiler=engine)
    second = load_library(RULES_DIR, compiler=engine)
    a = {rid: first.get(rid).bytecode_sha256 for rid in first.rule_ids()}
    b = {rid: second.get(rid).bytecode_sha256 for rid in second.rule_ids()}
    assert_eq(a, b)


# ---------------------------------------------------------------------------

print(f"\n{_passed} passed, {_failed} failed")
if hasattr(engine, "close"):
    engine.close()
sys.exit(1 if _failed else 0)
