"""RuleDSL MCP CLI tests - engine-free (no DLL, no `mcp` package needed).

Covers: --print-example-rules (discovery helper resolves a real library),
the Python 3.10 runtime-gate message logic, required-flags behavior, and
smoke's default rule-library resolution.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

sys.path.insert(0, str(REPO_ROOT / "bindings" / "python"))
from ruledsl_mcp.server import _python_version_error, example_rules_dir  # noqa: E402

# ---------------------------------------------------------------------------
# Test infrastructure (same harness style as the other mcp tests)
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


def run_server_cli(*argv):
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "bindings" / "python") + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [sys.executable, "-m", "ruledsl_mcp.server", *argv],
        capture_output=True, text=True, env=env)


# ---------------------------------------------------------------------------

@test("example_rules_dir resolves to a directory with a manifest")
def _():
    d = example_rules_dir()
    assert_true(d is not None, "no example library found")
    assert_true((Path(d) / "manifest.json").is_file(), "manifest.json missing")


@test("--print-example-rules prints that path and exits 0")
def _():
    proc = run_server_cli("--print-example-rules")
    assert_eq(proc.returncode, 0, proc.stderr)
    printed = Path(proc.stdout.strip())
    assert_true((printed / "manifest.json").is_file(),
                f"printed path has no manifest: {printed}")
    assert_eq(printed.resolve(), Path(example_rules_dir()).resolve())


@test("runtime gate: 3.10+ passes, 3.9 gets the clear message")
def _():
    assert_eq(_python_version_error((3, 10, 0)), None)
    assert_eq(_python_version_error((3, 12, 1)), None)
    message = _python_version_error((3, 9, 7))
    assert_true(message and "3.10+" in message and "3.9" in message,
                f"unhelpful gate message: {message!r}")
    assert_true("3.7+" in message, "message should point 3.7 users at the base package")


@test("required flags still enforced (exit 2, names the missing flags)")
def _():
    proc = run_server_cli()
    assert_eq(proc.returncode, 2)
    assert_true("required" in proc.stderr and "--rules" in proc.stderr,
                f"unexpected stderr: {proc.stderr}")


@test("smoke default rules resolution matches the discovery helper")
def _():
    from ruledsl_mcp import smoke
    assert_true(smoke.example_rules_dir is example_rules_dir,
                "smoke must reuse the server's resolver, not fork it")


# ---------------------------------------------------------------------------

print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
