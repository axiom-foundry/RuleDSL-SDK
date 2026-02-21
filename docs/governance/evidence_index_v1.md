# Evidence Bundle Index v1

## What is an evidence bundle?
An evidence bundle is a generated artifact set used to prove replay and determinism claims for a specific run context.
The repository stores tooling and specs; bundle artifacts are produced outside release payloads and archived separately.

## Minimum structure
A minimal bundle SHOULD include:
- `bytecode/`
- `records/`
- `reports/`
- `README.txt`
- `*.zip` (archive form of the bundle)

## Verification command (strict)
Use strict verification for production or audit checks:

```bash
python Tools/replay_proof/verify_replay_proof.py --a <a.json> --b <b.json> --out <report.json> --strict
```

## Bundle types
- `replay_proof_v1_demo_v4`
- `cross_platform_smoke_v1`

## Policy
Production and audit verification MUST use `--strict`.

## Cross-links
- RFC-001 system boundary: [`docs/governance/rfc_001_system_boundary_v1.md`](rfc_001_system_boundary_v1.md)
- RFC-001 test matrix: [`docs/governance/rfc_001_test_matrix_v1.md`](rfc_001_test_matrix_v1.md)
- RFC-002 determinism scope: [`docs/governance/rfc_002_determinism_scope_v1.md`](rfc_002_determinism_scope_v1.md)
- RFC-002 test matrix: [`docs/governance/rfc_002_test_matrix_v1.md`](rfc_002_test_matrix_v1.md)
- Audit answer template: [`docs/governance/audit_answer_template_replay_proof_v1.md`](audit_answer_template_replay_proof_v1.md)
- Cross-platform determinism smoke spec: [`docs/governance/cross_platform_determinism_smoke_v1.md`](cross_platform_determinism_smoke_v1.md)
- Replay proof tool README: [`Tools/replay_proof/README.md`](../../Tools/replay_proof/README.md)
- Replay proof schema: [`Tools/replay_proof/replay_proof_schema_v1.md`](../../Tools/replay_proof/replay_proof_schema_v1.md)
- Release tag: `v1.0.1-proofing` (Governance + replay proof hardening)