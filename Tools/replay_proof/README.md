# Replay Proof Verifier

`verify_replay_proof.py` verifies whether two evidence decision records are equal on the RFC-001 replay-proof surface.

It proves:
- equality of selected evidence fingerprints (engine/ABI, bytecode, decision/result hash, and conditional input/error code checks),
- deterministic replay comparison outcome (PASS/FAIL) with explicit mismatch fields.

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
