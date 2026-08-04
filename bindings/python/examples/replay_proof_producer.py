"""
Replay-Proof Producer Example — RuleDSL Python Binding

The SDK ships an offline verifier (`Tools/replay_proof/verify_replay_proof.py`)
that compares two `replay_proof_v1` decision records. This example shows the other
half: how a HOST/PRODUCER generates such a record from a real evaluation, so a
decision made today can be re-verified later (or on another machine).

A replay_proof_v1 record fingerprints an evaluation with hashes the producer
computes — the engine does not hand you a "decision hash"; choosing a canonical,
deterministic serialization of the decision is the producer's responsibility, and
this example shows one reasonable choice.

Usage:
    python replay_proof_producer.py <path-to-ruledsl-library> [out_dir]

It evaluates the same input twice and writes two records (run A, run B). Because
the engine is deterministic, the two records match — confirm it with:

    python ../../../Tools/replay_proof/verify_replay_proof.py --a <out>/run_a.json --b <out>/run_b.json --strict

This example passes no evaluation options, so its canonical options payload is
the empty JSON object (``{}``). A successful record is emitted only after the
binding accepts the arguments and the engine returns a decision; that path is
recorded as validation outcome ``OK`` with validation code ``0``.
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ruledsl import RuleDSL, CompileError, EvalError


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(obj) -> bytes:
    """Deterministic JSON: sorted keys, no insignificant whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _decision_payload(decision) -> dict:
    """One reasonable canonical view of a decision for hashing."""
    return {
        "matched": decision.matched,
        "action_type": decision.action_type,
        "amount": decision.amount,
        "currency": decision.currency,
        "window_count": decision.window_count,
        "window_unit": decision.window_unit,
        "rule_name": decision.rule_name,
        "outputs": decision.outputs,
    }


def make_replay_proof(engine, bytecode, fields) -> dict:
    """Run one evaluation and build a replay_proof_v1 record."""
    # This call supplies no explicit evaluation options. Hash the canonical
    # empty object instead of omitting the field: strict replay comparison must
    # distinguish "same options" from "options were not recorded".
    evaluation_options = {}
    decision = engine.evaluate(bytecode, fields)
    compat = engine.check_compatibility(bytecode)

    return {
        "schema_version": "replay_proof_v1",
        "engine_version_string": engine.version(),
        "abi_level": compat["minimum_engine_abi"],
        "bytecode_hash": _sha256_hex(bytecode.data),
        "decision_hash": _sha256_hex(_canonical_json(_decision_payload(decision))),
        # Strict evidence pins both inputs and the explicit evaluation options.
        "input_hash": _sha256_hex(_canonical_json(fields)),
        "options_hash": _sha256_hex(_canonical_json(evaluation_options)),
        # A record reaches this point only after binding validation and engine
        # evaluation succeed. These are producer/binding validation fields; the
        # engine does not emit them as part of AXDecision.
        "validation_outcome": "OK",
        "validation_code": 0,
        # informational, ignored by the verifier's equality check:
        "input_descriptor": "replay_proof_producer example",
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python replay_proof_producer.py <path-to-ruledsl-library> [out_dir]")
        return 2
    lib_path = sys.argv[1]
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)

    rule_source = """
        rule high_risk { when amount > 1000 and currency == "USD"; then decline; }
        rule allow_rest { when amount > 0; then allow; }
    """
    fields = {"amount": 1200.0, "currency": "USD"}

    with RuleDSL(lib_path) as engine:
        try:
            bytecode = engine.compile(rule_source)
        except CompileError as e:
            print(f"compile error: {e}")
            return 1

        try:
            # Same inputs, two independent evaluations -> two records that must match.
            rec_a = make_replay_proof(engine, bytecode, fields)
            rec_b = make_replay_proof(engine, bytecode, fields)
        except EvalError as e:
            print(f"eval error: {e}")
            return 1

    (out_dir / "run_a.json").write_text(json.dumps(rec_a, indent=2) + "\n", encoding="utf-8")
    (out_dir / "run_b.json").write_text(json.dumps(rec_b, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(rec_a, indent=2))
    print(f"\nwrote {out_dir/'run_a.json'} and {out_dir/'run_b.json'}")

    # The records are produced independently; for a deterministic engine they agree
    # on the fields the verifier checks for replay equality.
    strict_equality_fields = (
        "engine_version_string",
        "abi_level",
        "bytecode_hash",
        "decision_hash",
        "input_hash",
        "options_hash",
        "validation_outcome",
        "validation_code",
    )
    equal = all(rec_a[field] == rec_b[field] for field in strict_equality_fields)
    if not equal:
        print("UNEXPECTED: the two records disagree on replay-equality fields", file=sys.stderr)
        return 1
    print("REPLAY_PROOF_PRODUCED_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
