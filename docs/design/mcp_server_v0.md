# MCP Server v0 — Design (Phase 0)

Status: DRAFT / EXPERIMENTAL — design only, no implementation in this phase.
Applies to: RuleDSL engine v1.0.2+ (ABI level 1, `replay_proof_v1` era).

---

## 1. Purpose

Expose the RuleDSL engine to AI agents over the
[Model Context Protocol (MCP)](https://modelcontextprotocol.io) so that an
agent can *invoke* deterministic rule evaluation — never *produce* the
decision itself.

> **Thesis: "The agent invokes; the engine decides."**

The MCP server is a thin, deterministic invocation boundary. All decision
semantics remain inside the engine. The server adds no interpretation,
no heuristics, and no model-generated logic to the decision path.

---

## 2. Tool Surface (complete and closed)

The v0 server exposes exactly three tools. This list is closed: adding a
tool is a design change requiring a new revision of this document.

### 2.1 `list_rules`

- Input: none.
- Output: the set of callable rules from the rule-library manifest
  (see §6): for each rule, `rule_id`, `version`, `rule_sha256`.
- The server MUST NOT enumerate the filesystem; it reports only what the
  manifest declares.

### 2.2 `evaluate_case(rule_id, fields, now_utc_ms)`

- `rule_id` (string, required): must exist in the manifest; unknown ids
  fail with a stable error (§5), no fuzzy matching.
- `fields` (object, required): the case input handed to the engine
  unchanged. The server performs no coercion, defaulting, or enrichment.
- `now_utc_ms` (integer, required): the only time value in the system.
  See §3. It is handed to the engine as its own explicit evaluation
  parameter — never merged into `fields`; a `fields` key named
  `now_utc_ms` is rejected with `SRV_RESERVED_FIELD` (§5).
- Output: the decision-record for this evaluation (see §4), returned to
  the caller and appended to the JSONL decision log.

### 2.3 `engine_info`

- Input: none.
- Output: `engine_version` (e.g. `"1.0.2"`), ABI level, bytecode schema
  version, decision-record schema id, server package version, and the
  manifest hash currently loaded.

### 2.4 Non-goals (deliberately not exposed)

These are not "missing features". They are excluded because the
determinism boundary is embedded in the architecture: anything that lets
the agent influence *what* the decision logic is — rather than *which
declared rule* runs on *which explicit input* — moves decision authority
from the engine to the model.

| Excluded tool | Why it is not exposed |
|---|---|
| `decide(...)` (agent-mediated decision) | The decision must be a pure function of (rule bytecode, fields, now_utc_ms). A tool whose answer passes through the model reintroduces nondeterminism at the exact boundary this product exists to eliminate. |
| `write_rule(...)` | Rules enter the library through the reviewed compile/sign/manifest pipeline, not through a live agent session. A write path from the model would make the rule set an unauditable, session-dependent artifact. |
| `pick_rules(...)` (server-side rule selection) | Rule selection is a caller responsibility and must be explicit in the audit trail. If the server "helpfully" chose rules, the choice would be a hidden input to the decision. Deterministic routing is deferred, not smuggled in (§8). |
| Free-text compile / eval | Compiling model-generated text at decision time collapses the compile-time / run-time separation and bypasses hash pinning: the executed bytecode would have no pre-declared `rule_sha256`. |

---

## 3. Clock Policy

`now_utc_ms` is **mandatory and explicit** on every `evaluate_case` call.

- The server MUST NOT read the wall clock, monotonic clock, or any other
  ambient time source — not even as a default when the caller omits the
  parameter. Omission is a validation error and maps to the engine's own
  stable code for this condition, `AX_ERR_MISSING_NOW_UTC_MS` (§5).
- Rationale: ambient time is a *hidden-input class* defect. The v1.0.2
  release removed the last hidden filesystem input (the baked grammar
  path) from the engine binaries; the MCP layer must not reintroduce the
  same defect class through the back door with time.
- Consequence: identical `(rule_id, fields, now_utc_ms)` calls produce
  identical decision records (up to `engine_version`), and every
  recorded decision is replayable without clock simulation.

---

## 4. Decision-Record Schema (JSONL)

Every `evaluate_case` invocation appends exactly one JSON object as one
line to the decision log (JSONL). Fields:

| Field | Type | Meaning |
|---|---|---|
| `fields` | object | The case input, verbatim as received. |
| `rule_id` | string | Manifest id of the rule invoked. |
| `rule_sha256` | string | SHA-256 of the rule source, from the manifest. |
| `bytecode_sha256` | string | SHA-256 of the executed bytecode. |
| `decision` | object | The engine's decision payload. |
| `decision_hash` | string | Computed by the serving layer over the canonical decision payload, using the same canonicalization and payload shape as `replay_proof_v1` (Tools/replay_proof). Engine-side exposure of this hash through the C ABI is a v1+ binding enhancement. |
| `now_utc_ms` | integer | The explicit time input (§3). |
| `engine_version` | string | e.g. `"1.0.2"`. |

Records MUST NOT contain machine paths, usernames, hostnames, or any
timestamp other than the injected `now_utc_ms` (evidence-integrity rule).

**Relationship to `replay_proof_v1`:** this schema is a sibling of the
engine's internal `replay_proof_v1` decision-record convention — the
canonicalization and payload shape implemented by this repository's
replay tooling (`Tools/replay_proof`). It shares the hash-pinning
discipline (`bytecode_sha256` ↔ `bytecode_hash`, `decision_hash`,
`engine_version` ↔ `engine_version_string`) but is caller-facing: it
records *what was asked* (`fields`, `rule_id`, `now_utc_ms`) alongside
*what was decided*, whereas `replay_proof_v1` records engine-side
validation state (`options_hash`, `input_hash`, validation outcome).
A future revision may define a lossless mapping from an MCP decision
record to a `replay_proof_v1` record; v0 only requires that the two
never disagree on shared hashes for the same evaluation.

---

## 5. Error Taxonomy

MCP errors derive from the engine's existing numeric error contract
(`AXErrorCode` in `include/axiom/ruledsl_c.h`, append-only): the two
layers speak one language. Numeric codes are the contract; strings are
informational only.

Every failed tool call returns a stable error object:

```json
{ "error_domain": "engine" | "server", "error_code": <int>, "error_name": "<string>", "message": "<optional, informational>" }
```

- **`engine` domain**: `AXErrorCode` values passed through verbatim —
  the server never remaps, collapses, or renames an engine code. Any
  failure the engine already defines is reported with the engine's own
  code, e.g. `AX_ERR_MISSING_NOW_UTC_MS` (4) for an omitted
  `now_utc_ms`, `AX_ERR_INVALID_ARGUMENT` (1), `AX_ERR_NON_FINITE` (6),
  `AX_ERR_DIV_ZERO` (7), `AX_ERR_RUNTIME` (11),
  `AX_ERR_DUPLICATE_FIELD` (12). New engine codes flow through without
  a server change (unknown values are forwarded, not rejected).
- **`server` domain**: only for conditions the engine cannot see.
  Same discipline: stable numeric codes, append-only, never reused.
  v0 defines exactly one:

  | Code | Name | Condition |
  |---|---|---|
  | 1 | `SRV_UNKNOWN_RULE_ID` | `rule_id` not present in the manifest. |
  | 2 | `SRV_RESERVED_FIELD` | `fields` contains a key reserved for an explicit top-level parameter (v0: `now_utc_ms`). Silently overwriting or shadowing a caller-supplied value is a hidden-behavior class, so the call is rejected before reaching the engine. |

  (Manifest verification failure is not a call-time error: it is fatal
  at startup, §6.)

Failed evaluations produce **no** decision record in v0 — the JSONL log
(§4) contains successful decisions only. An error-record schema, if
needed, is a v1 topic and must not alter the v0 record schema.

---

## 6. Rule-Library Format

```text
rules/
  manifest.json
  <rule files referenced by the manifest>
```

- `manifest.json` carries a required top-level `manifest_version`
  (integer, starting at `1`) and maps
  `rule_id` → `{ file, sha256, version }`.
- The server accepts only `manifest_version` values it knows
  (v0: exactly `1`). An unknown or missing `manifest_version` is a
  fatal startup error — versions tell the truth; the server never
  guesses a format.
- **Only rules present in the manifest are callable.** A file under
  `rules/` that is not in the manifest does not exist as far as the
  server is concerned.
- On load, the server verifies each referenced file against its declared
  `sha256`; any mismatch is a fatal startup error (no partial serving).
- The manifest is read once at startup. Live mutation of the rule set is
  out of scope for v0; changing rules means restarting the server with a
  new manifest.
- Phase-1 note: rule bytecode is recompiled from source at every startup;
  there is no bytecode cache. Rationale: the compiler's output for the
  pinned engine version is the single source of truth — a cache would be
  a second artifact whose freshness would itself need verification.

---

## 7. Distribution

- Python packaging: optional extra `ruledsl[mcp]`, console entry point
  `ruledsl-mcp` — shipped by the [`ruledsl`](https://pypi.org/project/ruledsl/)
  package assembled from this repository's `bindings/python/`. The engine
  itself still ships as C ABI artifacts via Releases — see
  `docs/distribution.md`.
- CLI discovery helper: `ruledsl-mcp --print-example-rules` prints the
  shipped example rule-library path and exits — information only; `--rules`
  remains required and explicit (§2.2 discipline applies to paths too).
- Quickstart (setup, Claude Desktop config, e2e smoke client):
  `docs/mcp_quickstart.md`.
- **Experimental status:** the MCP server is explicitly EXPERIMENTAL in
  v0. It is not part of the release contract surface, carries no ABI or
  compatibility promise, and may change or be withdrawn without a major
  version bump of the engine.

---

## 8. Out of Scope (v1+)

- **Deterministic routing table**: a declarative, hash-pinned mapping
  from case shape → rule_id, so that rule selection itself becomes an
  auditable engine-side artifact. Deferred to keep v0's surface minimal;
  until then, rule selection stays with the caller (§2.4).
