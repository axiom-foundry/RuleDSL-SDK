"""
RuleDSL Quick Test — Run this immediately after receiving your SDK delivery packet.

This script validates that your SDK installation works end-to-end:
  1. Loads the shared library
  2. Creates and builds a compiler
  3. Compiles a minimal rule
  4. Verifies bytecode compatibility
  5. Evaluates against test input
  6. Checks the decision result

Usage:
    python quick_test.py path/to/ruledsl_capi.dll

Expected output:
    [PASS] Library loaded
    [PASS] Compiler created
    [PASS] Rule compiled (N bytes)
    [PASS] Bytecode compatible (axbc version 3)
    [PASS] Evaluation succeeded
    [PASS] Decision: DECLINE (rule: test_rule)
    ===== ALL CHECKS PASSED =====
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ruledsl import RuleDSL, Bytecode, RuleDSLError


def check(label, condition, detail=""):
    if condition:
        print(f"  [PASS] {label}" + (f" ({detail})" if detail else ""))
    else:
        print(f"  [FAIL] {label}" + (f" ({detail})" if detail else ""))
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python quick_test.py <path-to-ruledsl-library>")
        print("  e.g.: python quick_test.py ../../bin/ruledsl_capi.dll")
        sys.exit(1)

    lib_path = sys.argv[1]
    print(f"\nRuleDSL SDK Quick Test")
    print(f"Library: {lib_path}\n")

    # 1. Load library
    try:
        engine = RuleDSL(lib_path)
        check("Library loaded", True, engine.version())
    except Exception as e:
        check("Library loaded", False, str(e))

    # 2. Compile
    try:
        bytecode = engine.compile(
            'rule test_rule { when amount > 100; then decline; }'
        )
        check("Rule compiled", True, f"{len(bytecode)} bytes")
    except RuleDSLError as e:
        check("Rule compiled", False, str(e))

    # 3. Compatibility
    try:
        info = engine.check_compatibility(bytecode)
        check("Bytecode compatible", info["compatible"],
              f"axbc version {info['axbc_version']}")
    except RuleDSLError as e:
        check("Bytecode compatible", False, str(e))

    # 4. Evaluate — should DECLINE
    try:
        decision = engine.evaluate(bytecode, {
            "amount": 500.0,
        }, now_utc_ms=1700000000000.0)
        check("Evaluation succeeded", True)
        check(f"Decision: {decision.action}",
              decision.matched and decision.action == "DECLINE",
              f"rule: {decision.rule_name}")
    except RuleDSLError as e:
        check("Evaluation succeeded", False, str(e))

    # 5. Evaluate — should NOT match (amount too low)
    try:
        decision2 = engine.evaluate(bytecode, {
            "amount": 50.0,
        }, now_utc_ms=1700000000000.0)
        check("No-match case works", not decision2.matched, "amount=50 < 100")
    except RuleDSLError as e:
        check("No-match case works", False, str(e))

    engine.close()
    print(f"\n  ===== ALL CHECKS PASSED =====\n")


if __name__ == "__main__":
    main()
