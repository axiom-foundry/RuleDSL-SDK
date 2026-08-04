# Purchase Approval MCP Shadow Pilot

Status: **MCP 0.2.0 early access / EXPERIMENTAL**. This is one small,
opinionated proof-of-value for one SMB customer. It is not a general policy
platform, autonomous purchasing authority, authentication layer, daemon,
multi-tenant service, audit ledger, system of record, or 24/7 support offer.

The AI client can invoke exactly one manifest-visible policy id:
`purchase_approval`. Prioritized internal rules make the decision. The client
does not choose among unrelated policies and cannot create or change rules.

## Pilot decision contract

The host supplies all five fields and the mandatory top-level `now_utc_ms`.
The manifest is v2, closed with `additionalProperties:false`, and validates all
fields before the engine runs.

| Field | Contract |
|---|---|
| `amount_minor` | JSON integer, `1..9007199254740991`, in minor currency units |
| `currency` | `TRY`, `USD`, or `EUR` |
| `supplier_status` | `approved`, `new`, or `blocked` |
| `budget_available` | JSON boolean |
| `manual_review_required` | JSON boolean |

`amount_minor` avoids floating-point currency input: zero and negative values are
typed validation errors. `500000` means TRY 5,000.00 when the host uses kuruş
as its minor unit. The pilot limit is exactly
`500000`; `500000` can be allowed and `500001` is reviewed. The policy checks
`currency == "TRY"` explicitly. Currency metadata alone does not enforce a
currency, so declared non-TRY examples (`USD`, `EUR`) route to review.

Priority order:

1. blocked supplier -> `DECLINE / procurement_reject`;
2. non-TRY currency -> `REVIEW / human_review`;
3. amount above `500000` -> `REVIEW / human_review`;
4. unavailable budget -> `REVIEW / human_review`;
5. new supplier -> `REVIEW / human_review`;
6. manual-review flag -> `REVIEW / human_review`;
7. only approved + budget + TRY + at/below limit + no manual flag ->
   `ALLOW / straight_through`;
8. final `when true` catch-all -> `REVIEW / human_review`.

Every outcome has an explicit `reason` and `route`. Shipped v0.9 `and`/`or`
does not short-circuit: both operands are evaluated. This pack is safe because
every referenced field is required and schema-validated, not because a left
operand protects a later field access.

## Run the acceptance verifier

Prerequisites: Python 3.10+, the RuleDSL Python package 1.2.0 with MCP 0.2.0,
and the hash-verified engine v1.0.2 bundle for your platform. The engine binary
is separate from the Python package. Verify the bundle using its published
`SHA256SUMS.txt` before using the library under `bin/`.

Clone the SDK to obtain this pilot pack, then use the published Python package:

```bash
git clone https://github.com/axiom-foundry/RuleDSL-SDK.git
cd RuleDSL-SDK
python3 -m venv .venv
. .venv/bin/activate
python -m pip install "ruledsl[mcp]==1.2.0" \
  -c Tools/ci/constraints-mcp-2.0.0.txt
python examples/mcp_pilot/verify_pilot.py \
  --engine-lib /absolute/path/to/bundle/bin/libruledsl_capi.so \
  --receipt ./pilot-acceptance-receipt.json
```

```powershell
git clone https://github.com/axiom-foundry/RuleDSL-SDK.git
Set-Location RuleDSL-SDK
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install "ruledsl[mcp]==1.2.0" `
  -c Tools/ci/constraints-mcp-2.0.0.txt
python .\examples\mcp_pilot\verify_pilot.py `
  --engine-lib C:\absolute\path\to\bundle\bin\ruledsl_capi.dll `
  --receipt .\pilot-acceptance-receipt.json
```

`--receipt` is optional and refuses to overwrite an existing file. It contains
only bounded technical acceptance evidence: engine/server/manifest/rule
identity, case results, and decision hashes. It contains no wall-clock read,
secret, customer input, whole-record hash, hash chain, audit-completeness
claim, or system-of-record claim.

For source-development instead of the published package, install the pinned
MCP SDK and expose the checkout wrapper explicitly:

```bash
python -m pip install "mcp==2.0.0" -c Tools/ci/constraints-mcp-2.0.0.txt
export PYTHONPATH="$PWD/bindings/python"
python examples/mcp_pilot/verify_pilot.py \
  --engine-lib /absolute/path/to/bundle/bin/libruledsl_capi.so \
  --wrapper "$PWD/bindings/python"
```

The verifier starts the real server over JSON-RPC/stdio. It asserts the closed
three-tool list, one listed rule and its schema, engine identity, eight positive
decisions and their committed golden hashes, the exact threshold boundary,
one repeated byte-identical record, eight typed rejections with no log append,
and a success-only decision log matching the returned records.

## Claude Desktop-style configuration

Use absolute paths. The server itself never chooses the rules, log, engine, or
clock. Example for a venv containing the published package:

```json
{
  "mcpServers": {
    "ruledsl-purchase-pilot": {
      "command": "/ABSOLUTE/PATH/TO/.venv/bin/ruledsl-mcp",
      "args": [
        "--rules", "/ABSOLUTE/PATH/TO/RuleDSL-SDK/examples/mcp_pilot/rules",
        "--decision-log", "/ABSOLUTE/PATH/TO/pilot-decisions.jsonl",
        "--engine-lib", "/ABSOLUTE/PATH/TO/bundle/bin/libruledsl_capi.so"
      ]
    }
  }
}
```

On Windows, `command` is
`C:\\ABSOLUTE\\PATH\\TO\\.venv\\Scripts\\ruledsl-mcp.exe`; use escaped
backslashes for every JSON path and point `--engine-lib` at
`ruledsl_capi.dll`.

The trusted host supplies `now_utc_ms` as a JSON integer argument on every
`evaluate_case` call. It is not a field, and the AI client must not invent it
from prose or read a clock implicitly.

## Shadow-pilot operations checklist

- [ ] One customer tenant, one server process, and one MCP client connection.
- [ ] Host allowlist is pinned to rule id `purchase_approval`; reject any other
      id before invoking MCP.
- [ ] Trusted host supplies `now_utc_ms` and the five typed fields from known
      system values, not unreviewed free text.
- [ ] Any MCP transport/tool/schema/engine error maps to `NO_DECISION` and a
      human-review route. Never convert an error into ALLOW.
- [ ] Host logs its request id, principal, tenant, and failure outcome. The MCP
      decision log does not provide those identities and does not log failures.
- [ ] Define PII/secret redaction before the pilot; configure retention and
      rotation for host logs and the MCP decision-record file.
- [ ] Existing purchasing workflow remains the authority for 2–4 weeks. MCP
      results are compared in shadow mode and do not execute purchases.
- [ ] Review false positives/negatives and boundary cases with the customer's
      process owner before changing the rule source or manifest hash.
- [ ] Rollback is operationally simple: stop invoking MCP. The existing system
      remains authoritative; no data migration or daemon shutdown is required.

This checklist is an integration aid, not an SLA or managed-service promise.