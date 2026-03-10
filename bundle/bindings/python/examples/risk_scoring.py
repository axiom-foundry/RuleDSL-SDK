"""
Risk Scoring Example — RuleDSL Python Binding

This example demonstrates:
1. Compiling a rule from source
2. Evaluating transactions against the rule
3. Handling the decision result

Usage:
    python risk_scoring.py path/to/ruledsl_capi.dll
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import ruledsl
sys.path.insert(0, str(Path(__file__).parent.parent))
from ruledsl import RuleDSL, CompileError, EvalError


def main():
    if len(sys.argv) < 2:
        print("Usage: python risk_scoring.py <path-to-ruledsl-library>")
        print("  e.g.: python risk_scoring.py ../../bin/ruledsl_capi.dll")
        sys.exit(1)

    lib_path = sys.argv[1]

    with RuleDSL(lib_path) as engine:
        print(f"Engine version: {engine.version()}")

        # Compile risk scoring rules
        rule_source = """
            rule high_risk_transaction {
                when amount > 1000 and currency == "USD";
                then decline;
            }

            rule medium_risk_transaction {
                when amount > 500;
                then review;
            }

            rule default_allow {
                when amount > 0;
                then allow;
            }
        """

        try:
            bytecode = engine.compile(rule_source)
            print(f"Compiled successfully ({len(bytecode)} bytes)")
        except CompileError as e:
            print(f"Compile error: {e}")
            sys.exit(1)

        # Test transactions
        transactions = [
            {"amount": 1200.0, "currency": "USD"},   # Should DECLINE
            {"amount": 800.0, "currency": "EUR"},     # Should REVIEW
            {"amount": 50.0, "currency": "USD"},      # Should ALLOW
        ]

        print("\n--- Evaluating transactions ---")
        for i, tx in enumerate(transactions, 1):
            try:
                decision = engine.evaluate(bytecode, tx)
                print(f"TX {i}: amount={tx['amount']} {tx['currency']} "
                      f"-> {decision.action} "
                      f"(rule: {decision.rule_name or 'none'})")
            except EvalError as e:
                print(f"TX {i}: ERROR {e.code_name}: {e}")


if __name__ == "__main__":
    main()
