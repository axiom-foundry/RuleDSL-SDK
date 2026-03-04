# RuleDSL SDK (C API)

RuleDSL is a **deterministic rule-evaluation engine** embedded via a stable C ABI.
Same input, same bytecode, same decision — guaranteed across supported platforms.

**Use cases**: transaction risk scoring, spending-limit enforcement, compliance gating, offer eligibility, real-time policy evaluation.

**What it is**: an in-process library (`.dll` / `.so`). No daemon, no network hop, no database dependency.

**What it is not**: not a SaaS, not an open-source engine, not a 24/7 managed service.

## Quickstart

Customer workflow: **Write -> Compile -> Verify -> Evaluate**

```
# 1. Write a rule
rule high_risk {
    when amount > 1000 and currency == "USD";
    then decline;
}

# 2. Compile to bytecode
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3

# 3. Verify bytecode integrity
ruledslc verify rules.axbc

# 4. Evaluate via C API (see examples/)
```

Minimal C integration:

```c
#include "axiom/ruledsl_c.h"

char err[256] = {0};
AXCompiler* c = ax_compiler_create();
ax_compiler_build(c, err, sizeof(err));

// Load bytecode from file (see examples/c/minimal_eval.c for full load_file helper)
AXBytecode bc = {0};
// ... load .axbc file into bc.data / bc.size ...

AXField fields[] = {
    { "amount",     { AX_VALUE_NUMBER, .number = 1200.0 } },
    { "currency",   { AX_VALUE_STRING, .text = "USD" } },
    { "now_utc_ms", { AX_VALUE_NUMBER, .number = 1700000000000.0 } },
};

AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
AXDecision dec = AX_DECISION_INIT;

AXErrorCode code = ax_eval_bytecode(c, &bc, fields, 3, &opts, &dec, err, sizeof(err));
if (code == AX_ERR_OK && dec.matched) {
    printf("Decision: %d\n", dec.action_type);  // AX_ACTION_DECLINE
}

ax_decision_reset(&dec);
ax_compiler_destroy(c);
```

## What you receive

A delivery packet includes:

| Content | Source |
|---------|--------|
| `include/` C headers | This repository |
| `bin/` compiled binaries | Provided separately |
| `manifest.json` + `SHA256SUMS.txt` | Integrity verification |
| Documentation | This repository |
| Examples | `examples/` directory |

## Language bindings

Not a C developer? Use the ready-made wrappers:

| Language | Location | Dependencies |
|----------|----------|-------------|
| Python 3.7+ | [`bindings/python/`](bindings/python/README.md) | None (pure ctypes) |
| C# (.NET 6+) | [`bindings/csharp/`](bindings/csharp/README.md) | None (P/Invoke) |

## Essential docs

| Topic | Document |
|-------|----------|
| Integration examples | [`docs/integration_snippets.md`](docs/integration_snippets.md) |
| Error handling | [`docs/errors.md`](docs/errors.md) |
| Troubleshooting | [`docs/troubleshooting.md`](docs/troubleshooting.md) |
| Version policy | [`docs/version_policy.md`](docs/version_policy.md) |
| Support policy | [`docs/support_policy.md`](docs/support_policy.md) |
| Compatibility matrix | [`docs/compatibility_matrix.md`](docs/compatibility_matrix.md) |
| Distribution + verification | [`docs/distribution.md`](docs/distribution.md) |

## Language specification (v0.9)

| Document | Link |
|----------|------|
| Full specification | [`docs/language/spec_v0_9.md`](docs/language/spec_v0_9.md) |
| Grammar (EBNF) | [`docs/language/grammar_v0_9.md`](docs/language/grammar_v0_9.md) |
| Lexical core | [`docs/language/lexical_core_v0_9.md`](docs/language/lexical_core_v0_9.md) |
| Numeric model | [`docs/language/numeric_model_v0_9.md`](docs/language/numeric_model_v0_9.md) |
| Conformance status | [`docs/language/status_v0_9.md`](docs/language/status_v0_9.md) |

## Contracts (frozen v1.0)

| Contract | Link |
|----------|------|
| Determinism | [`docs/contracts/determinism_contract_v1_0.md`](docs/contracts/determinism_contract_v1_0.md) |
| Error codes registry | [`docs/contracts/error_codes_registry_v1_0.md`](docs/contracts/error_codes_registry_v1_0.md) |
| Input canonicalization | [`docs/contracts/input_canonicalization_v1_0.md`](docs/contracts/input_canonicalization_v1_0.md) |
| Evidence bundle | [`docs/contracts/determinism_evidence_bundle_v1_0.md`](docs/contracts/determinism_evidence_bundle_v1_0.md) |
| Error mapping annex | [`docs/contracts/error_mapping_annex_v1_0.md`](docs/contracts/error_mapping_annex_v1_0.md) |

## Operational docs

| Topic | Link |
|-------|------|
| Evaluation playbook (30-day) | [`docs/evaluation_playbook.md`](docs/evaluation_playbook.md) |
| Bytecode lifecycle | [`docs/bytecode_lifecycle.md`](docs/bytecode_lifecycle.md) |
| Release gate | [`docs/release_gate.md`](docs/release_gate.md) |
| Signing policy | [`docs/signing_policy.md`](docs/signing_policy.md) |
| Compiler contract | [`docs/compiler/ruledslc_contract.md`](docs/compiler/ruledslc_contract.md) |

## Distribution & verification

| Document | Link |
|----------|------|
| Distribution runbook | [`docs/distribution/runbook.md`](docs/distribution/runbook.md) |
| Bundle standard | [`docs/distribution/bundle_standard.md`](docs/distribution/bundle_standard.md) |
| Customer verification | [`docs/distribution/customer_verification.md`](docs/distribution/customer_verification.md) |

## Architecture & governance

| Document | Link |
|----------|------|
| Freeze charter | [`docs/architecture/architectural_freeze_charter_v1_0.md`](docs/architecture/architectural_freeze_charter_v1_0.md) |
| ABI evolution contract | [`docs/architecture/c_api_abi_evolution_contract_v1.md`](docs/architecture/c_api_abi_evolution_contract_v1.md) |
| ADR index | [`docs/adr/README.md`](docs/adr/README.md) |
| Contract gate policy | [`docs/governance/contract_gate.md`](docs/governance/contract_gate.md) |
| Release model | [`docs/governance/release_model.md`](docs/governance/release_model.md) |
| RFC-001 System boundary | [`docs/governance/rfc_001_system_boundary_v1.md`](docs/governance/rfc_001_system_boundary_v1.md) |
| RFC-002 Determinism scope | [`docs/governance/rfc_002_determinism_scope_v1.md`](docs/governance/rfc_002_determinism_scope_v1.md) |

## Release model

RuleDSL follows a three-lane release model:

1. **Stable** (e.g. `v1.0.0`) — ABI-stable, production-ready, marked as "Latest"
2. **Proofing** (e.g. `v1.0.1-proofing`) — governance and tooling validation, pre-release only
3. **Phase markers** (e.g. `governance-spine-v1`) — architectural milestones, pre-release only

This separation keeps product stability independent from governance evolution.
