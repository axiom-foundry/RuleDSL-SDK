# RuleDSL SDK (PUBLIC) – Claude Execution Rules

This repository is the **public-facing SDK surface** for RuleDSL.
It contains ONLY: C headers, documentation, examples, governance artifacts, and tooling scripts.
No engine source code exists here.

---

## Project Context

- **Product**: RuleDSL — deterministic, in-process business rule engine (C ABI)
- **Owner**: Solo founder (domain expert, not full-time developer)
- **Target market**: SMB companies needing embedded policy/rule evaluation
- **Distribution**: Commercial SDK — headers + compiled binaries delivered as versioned packets
- **Private repo**: `C:\dev\AXIOM` (engine source, compiler, tests — NEVER referenced in public commits)
- **Current version**: 1.0.0 (SDK), language v1.0, ABI level 1

---

## Repo Structure

```
include/axiom/          # Public C API headers (frozen ABI surface)
  ruledsl_c.h           # Main API: 15 functions, 7 types, 12 error codes
  export.h              # AXIOM_API visibility macros
  version.h             # Version constants (1.0.0)
docs/                   # All public documentation
  language/             # RuleDSL v1.0 spec, grammar, lexical, numeric model
  contracts/            # Determinism, error codes, canonicalization (frozen v1.0)
  governance/           # ADRs, RFCs, contract gates, release model
  architecture/         # Freeze charter, ABI evolution, replay/evidence
  distribution/         # Bundle standard, runbook, customer verification
  adr/                  # Architecture Decision Records (4 accepted)
  evidence/             # Governance snapshots, audit summaries
  compiler/             # ruledslc CLI contract, authenticity policy
examples/               # Customer-facing integration examples (C)
  01_risk_scoring/      # Full example with .rule, .axbc, main.c
  02_threshold_gate/
  03_temporal_rule/
  c/minimal_eval.c      # Minimal integration snippet
Tools/                  # Automation scripts (Python, PowerShell)
  replay_proof/         # Determinism proof verifier
  release_bundle/       # Bundle assembly + audit
  smoke/                # Compiler smoke test
  public_surface_hash/  # Header drift detection
  release_guard/        # Release tag policy enforcement
  evidence_sanity/      # Evidence artifact scanner
reports/                # Build/audit/merge reports (historical)
```

---

## Absolute Constraints

1. **No engine source code** — This repo never contains C++ implementation files.
2. **No private repo references** — Never mention `AXIOM`, `Core/`, `Products/`, or internal paths in commits/docs.
3. **Frozen ABI surface** — `include/axiom/*.h` changes require `Contract change: YES` in PR body.
4. **Frozen error codes** — `AXErrorCode` numeric values (0–11) are permanent within MAJOR 1.x.
5. **Determinism is a hard contract** — No implicit time, no locale, no randomness, no fast-math.
6. **Headers mirror from private repo** — Public headers must exactly match `AXIOM/SDK/Include/axiom/`.
7. **Stop on first failure** — Do not continue past errors; ask for clarification.
8. **Do not expand scope** — Only change what is explicitly requested.

---

## Design Principles (Business Context)

This SDK is operated by a solo founder who cannot provide 24/7 support.
Every design decision must optimize for **minimal support burden**:

- **Self-explanatory errors**: 12 stable numeric codes + diagnostic strings. Customers branch on codes, log details.
- **Defensive API**: struct_size checks, null guards, clear ownership rules prevent most misuse.
- **Determinism guarantee**: Same input → same output eliminates "works on my machine" tickets.
- **Explicit memory contract**: Caller owns structs, SDK owns internal strings. No ambiguity.
- **Forward-compatible ABI**: reserved fields + struct_size pattern means minor upgrades don't break customers.
- **Structured evaluation**: 30-day eval process with documented success criteria reduces premature adoption.

---

## Key API Surface (Quick Reference)

```
Lifecycle:     ax_compiler_create → ax_compiler_build → [use] → ax_compiler_destroy
Compile:       ax_compile_to_bytecode(compiler, input, &bytecode, err, err_len)
Verify:        ax_check_bytecode_compatibility(data, size, &info) → AXStatus
Evaluate:      ax_eval_bytecode(compiler, bytecode, fields, count, &opts, &decision, err, err_len) → AXErrorCode
Cleanup:       ax_decision_reset(&decision), ax_bytecode_free(&bytecode)
Diagnostics:   ax_error_to_string(code), ax_last_error_detail_utf8(buf, cap), ax_clear_last_error()
Version:       ax_version_string()
```

Required field: `now_utc_ms` (epoch ms as number) — engine never reads wall-clock.

---

## Error Codes (Frozen)

| Code | Value | Category |
|------|------:|----------|
| AX_ERR_OK | 0 | Success |
| AX_ERR_INVALID_ARGUMENT | 1 | Caller misuse |
| AX_ERR_COMPILE | 2 | Rule compilation failure |
| AX_ERR_VERIFY | 3 | Bytecode integrity failure |
| AX_ERR_MISSING_NOW_UTC_MS | 4 | Required time field absent |
| AX_ERR_NOW_UTC_MS_NOT_NUMBER | 5 | Time field wrong type |
| AX_ERR_NON_FINITE | 6 | NaN/Inf rejected |
| AX_ERR_DIV_ZERO | 7 | Division by zero |
| AX_ERR_CONCURRENT_COMPILER_USE | 8 | Thread safety violation |
| AX_ERR_LIMIT_EXCEEDED | 9 | Engine limits hit |
| AX_ERR_BAD_STRUCT_SIZE | 10 | ABI mismatch |
| AX_ERR_RUNTIME | 11 | Generic runtime error |

---

## Governance Model

- **Contract gate**: PRs touching frozen surfaces need explicit declaration
- **Public surface manifest**: SHA-256 hash of headers, drift-checked by CI
- **Release model**: 3-lane (stable / proofing / phase-marker)
- **ADRs**: 4 accepted (ABI evolution, error contract, replay schema, determinism boundary)
- **Evidence discipline**: No host paths, usernames, or real timestamps in artifacts

---

## Build & CI Notes

- No compilation happens in this repo (headers-only + docs + scripts)
- Tools are Python/PowerShell for validation and bundling
- CI workflows were previously in `.github/workflows/` (currently deleted from working tree)
- Local validation: `python Tools/public_surface_hash/gen_manifest.py --check`

---

## Documentation Standards

- Customer-facing docs use clear, direct language
- No internal jargon or private repo references
- Error messages must be actionable without vendor support
- Examples must compile and run against any compatible SDK delivery packet

---

## If Uncertain

- Ask for clarification before acting
- Choose the smallest safe change
- Quality > speed
- Determinism > convenience
- Correctness > cleverness
