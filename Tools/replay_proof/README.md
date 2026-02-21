# Replay Proof Verifier

`verify_replay_proof.py` verifies whether two evidence decision records are equal on the RFC-001 replay-proof surface.

It proves:
- equality of selected evidence fingerprints (engine/ABI, bytecode, decision/result hash, and conditional input/options/validation/error checks),
- deterministic replay comparison outcome (PASS/FAIL) with explicit mismatch fields.


Strict mode policy:
- requires `input_hash`, `options_hash`, `validation_outcome`, and `validation_code` in both records;
- compares those fields and fails on any mismatch.

It does NOT prove:
- rule execution correctness,
- semantic equivalence beyond the provided hashes,
- engine-internal behavior not represented in the input records.

Usage:

```powershell
python Tools/replay_proof/verify_replay_proof.py --a <recordA.json> --b <recordB.json> [--out <report.json>] [--strict]
```

Exit codes:
- `0`: PASS
- `1`: invalid input/schema
- `2`: mismatch
