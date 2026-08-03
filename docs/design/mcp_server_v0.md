# MCP Server v0 — Design (Phase 0)

Status: EXPERIMENTAL — implemented and shipped as `ruledsl_mcp`
(see docs/mcp_quickstart.md). Revision 2: manifest v2 with per-rule input
schemas, explicit tool schemas, `isError` failures, server codes 3–9.
Applies to: RuleDSL engine v1.0.2+ (ABI level 1, `replay_proof_v1` era).
The surface remains EXPERIMENTAL (§7): no ABI or compatibility promise.

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
  (see §6): for each rule, `rule_id`, `version`, `rule_sha256`, and
  `input_schema`.
- `input_schema` is not a convenience. `evaluate_case` rejects any field a
  rule does not declare (§2.2), so this listing is the only way a caller
  can construct a call the server will accept.
- The server MUST NOT enumerate the filesystem; it reports only what the
  manifest declares.

### 2.2 `evaluate_case(rule_id, fields, now_utc_ms)`

- `rule_id` (string, required): must exist in the manifest; unknown ids
  fail with a stable error (§5), no fuzzy matching.
- `fields` (object, required): the case input handed to the engine
  unchanged. The server performs no coercion, defaulting, or enrichment —
  **and accepts no value the engine cannot receive faithfully.** Every
  field is checked against the rule's declared `input_schema` (§6) and
  against the value-safety rules in §5 before the engine is called. A
  value that would cross the `AXValue` boundary altered (a string
  containing NUL, an integer beyond 2^53−1) is refused, not adjusted:
  the alternative is a decision record that describes an input the engine
  never evaluated.
- `now_utc_ms` (integer, required): the only time value in the system.
  See §3. Advertised as `"type": "integer"` and enforced as one — a
  numeric string is rejected (`AX_ERR_NOW_UTC_MS_NOT_NUMBER`, 5), never
  coerced; a fractional value, one beyond 2^53−1, or a negative one is
  `SRV_NOW_UTC_MS_NOT_INTEGER` (7); omission remains
  `AX_ERR_MISSING_NOW_UTC_MS` (4). It is handed to the engine as its own
  explicit evaluation parameter — never merged into `fields`; a `fields`
  key named `now_utc_ms` is rejected with `SRV_RESERVED_FIELD` (§5).
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

### 2.5 Tool schemas

Every tool advertises a hand-written `inputSchema` and `outputSchema`. They
are not derived from the implementation's type annotations, because that
derivation is actively wrong here: the SDK's argument model coerces in lax
mode, so a declared numeric parameter silently accepts a numeric *string* —
exactly the input this server must refuse — and turns an integer into a
float, so the same evaluation would produce a different decision record over
the wire than in process.

- Successful results carry `structuredContent` equal to the tool's return
  object, with no `{"result": …}` wrapper.
- `list_rules` returns each rule's `input_schema`. It is the only way a
  caller can construct a call this server will accept, so discovery has to
  carry the contract.
- Arguments are a closed set: an argument a tool does not declare is
  rejected with `SRV_UNKNOWN_ARGUMENT` (9), never ignored. Silently
  dropping part of a caller's request is the same class of defect as
  silently coercing it — a misspelled `now_utc_ms` must not read as absent.
- The server **refuses to start** if the transport SDK will not accept the
  explicit schemas. Advertising a contract it does not honour, or honouring
  one it does not advertise, is worse than failing loudly.
- **The server enforces the advertised `outputSchema` itself.** The SDK does
  not: it validates a successful result against a model derived from the tool
  function's return annotation, which is a different object from the schema
  attached to the tool and shown by `tools/list`. Every result is therefore
  checked here against the published schema, and for `evaluate_case` the check
  runs *before* the decision record is written — a violation is
  `SRV_INTERNAL` (8) with nothing logged, so a record can never contradict the
  response its caller received.

### 2.6 Error transport

- A failed call returns `isError: true`. It is never delivered as a
  successful call carrying an error-shaped payload: an orchestrator that
  checks only transport success would count that as a decision.
- The §5 error object is carried in **both** `structuredContent` and a text
  content block, and the two always agree. A client branches on the
  structured form; it never has to parse prose.
- A failed call produces no `structuredContent` decision and no decision
  record (§4).
- **Top-level argument types are checked on the RAW request, before the SDK
  touches it.** This is not defence in depth; it is the only place the check
  works. The SDK pre-parses any string argument whose annotation is not `str`
  with `json.loads` (`pre_parse_json`, `mcp/server/mcpserver/utilities/
  func_metadata.py`), and this server annotates its parameters `Any`
  precisely so Pydantic will not coerce — so `Any is not str` and a caller
  sending `fields='{"amount":1}'` had it turned into a real object before any
  validation ran. Validation that runs after coercion is not validation. The
  wire and a direct in-process call share one implementation of this check,
  so they cannot drift.
- The transport SDK is pinned to the 2.x line. The 1.x/FastMCP path was
  removed rather than maintained, because it could not produce this shape:
  supporting both would have meant shipping two different error contracts.
  The declared range is `mcp>=2.0,<3`, but **the range is permission, not
  evidence**: only the versions CI installs — pinned exactly, with their
  transitive closure pinned in `Tools/ci/constraints-mcp-<version>.txt` — are
  verified. Today that is `2.0.0`, which is the whole 2.x line so far.

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

Schema id: `mcp_decision_record_v1` (was `mcp_decision_record_v0`), reported
by `engine_info`. What changed: `now_utc_ms` is always a JSON integer -
an integral float such as `1700000000000.0` is normalized to the integer
`1700000000000`, so the two spellings of one instant produce a
byte-identical record instead of two different lines - and
every field value is guaranteed exactly representable by the engine, so the
record and the engine's view of the input can no longer disagree. The field
list and the decision payload are unchanged.

### 4.1 This is a decision record, not an audit ledger

Stated plainly so nothing here is read as a stronger claim than it is.

**Guaranteed:** in a successfully written record, `fields` and `now_utc_ms`
are exactly what the engine evaluated. Every value that would reach the
engine altered is refused before evaluation (§2.2, §5), so the record cannot
describe an input other than the one that produced the decision.

**Not provided, and not claimed:**

- atomicity or ordering between concurrent writers (there is no writer lock,
  and no sequence number to reconstruct order after the fact);
- durability against a partial write — records are flushed, not `fsync`ed;
- caller identity: no request id, principal, or tenant;
- integrity over the whole record: `decision_hash` covers the decision
  payload only, and records are not chained;
- any record of failed calls (see the end of §5);
- PII redaction — `fields` is written verbatim;
- size or rotation limits on the log file.

A ledger with those properties is separate work. Until it exists, treat this
file as evidence *of a decision*, not as the system of record.

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
{
  "error_domain": "engine" | "server",
  "error_code": <int>,
  "error_name": "<string>",
  "message": "<optional, informational>",
  "field": "<dotted path of the rejected input, or null>"
}
```

`field` names what was rejected — `"fields.amount"`, `"now_utc_ms"`,
`"rule_id"`, or an argument name — and is `null` for errors not scoped to a
single input. The key is **always present**, so a client never has to test
for it, and an agent can correct itself without parsing the message.

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
  Codes 1–9 are defined:

  | Code | Name | Condition |
  |---|---|---|
  | 1 | `SRV_UNKNOWN_RULE_ID` | `rule_id` not present in the manifest. |
  | 2 | `SRV_RESERVED_FIELD` | `fields` contains a key reserved for an explicit top-level parameter (`now_utc_ms`). Silently overwriting or shadowing a caller-supplied value is a hidden-behavior class, so the call is rejected before reaching the engine. |
  | 3 | `SRV_FIELDS_TOO_LARGE` | A declared bound in §9 is exceeded. The message never echoes the oversized value. |
  | 4 | `SRV_UNSAFE_FIELD_VALUE` | A value the engine cannot receive faithfully: a string containing U+0000 (C strings truncate), an integer beyond ±(2^53−1) (binary64 rounds), or a value with no `AXValue` representation (object, array, …). |
  | 5 | `SRV_FIELD_NAME_INVALID` | A `fields` key that is not a non-empty string, or contains U+0000. |
  | 6 | `SRV_SCHEMA_VIOLATION` | `fields` does not satisfy the rule's declared `input_schema` (§6): an undeclared key, a missing required key, or a `type`/`enum`/`minimum`/`maximum`/`minLength`/`maxLength` violation. |
  | 7 | `SRV_NOW_UTC_MS_NOT_INTEGER` | `now_utc_ms` is numeric but not a valid whole millisecond: fractional, above 2^53-1, or negative. Negative is included because the advertised schema declares `minimum: 0` - honouring a wider range than the one published is the same defect as publishing one the server does not honour. Non-numeric keeps `AX_ERR_NOW_UTC_MS_NOT_NUMBER` (5); omission keeps `AX_ERR_MISSING_NOW_UTC_MS` (4). |
  | 8 | `SRV_INTERNAL` | A server invariant the implementation itself forbids (a library entry with no bytecode, an unparseable engine version string, a drifted decision-record shape). Never expected; reported through the error contract rather than escaping as an untyped crash. |
  | 9 | `SRV_UNKNOWN_ARGUMENT` | A top-level call argument the tool does not declare (§2.5). |

  **Value fidelity and code choice.** Codes 3–6 exist because the engine
  cannot see these conditions: by the time a NUL-truncated string or a
  rounded integer reaches it, the damage is already done and looks like
  ordinary input. A non-finite number is different — the engine defines
  `AX_ERR_NON_FINITE` (6) for it — so it is reported in the `engine` domain,
  per the rule above.

  Why this matters more than it looks: shipped v0.9 compares across types
  silently and applies no static type checking
  (`docs/language/conformance_status_v0_9.md`). An unvalidated `"2000"`
  therefore does not fail — it matches no threshold and falls through to
  whatever rule catches everything. Validation is what turns a type mistake
  into an error instead of a wrong decision.

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
  (integer) and maps
  `rule_id` → `{ file, sha256, version, input_schema }`.
- The server accepts only `manifest_version` values it knows
  (currently: exactly `2`). An unknown or missing `manifest_version` is a
  fatal startup error — versions tell the truth; the server never
  guesses a format.
- **`manifest_version` 1 is refused, not tolerated.** A v1 manifest
  declares no `input_schema`, so serving one would keep the unvalidated
  input path alive under a "supported" banner — and that path is the
  fail-open this revision exists to close.

### 6.1 `input_schema` (required, per rule)

Each rule declares the shape of the case it accepts. `evaluate_case`
enforces it before the engine runs (§2.2), so a rule can no longer be
invoked with a case it was never written for.

**Why in the manifest rather than beside it:** the manifest is already
hashed and its `manifest_sha256` is reported by `engine_info`. Putting the
schemas inside it makes the input contracts tamper-evident at no extra
cost, with nothing new to verify.

Supported keywords — a deliberately small JSON Schema subset:

| Where | Keyword | Rule |
|---|---|---|
| root | `type` | required; must be exactly `"object"` |
| root | `properties` | required; object, may be empty |
| root | `required` | array of strings, each named in `properties` |
| root | `additionalProperties` | absent or literal `false` — the closed world IS the contract |
| field | `type` | **required**; `number`, `integer`, `string`, `boolean`, `null`, or a list of those |
| field | `enum` | non-empty array of scalars the declared type allows |
| field | `minimum` / `maximum` | numeric types only |
| field | `minLength` / `maxLength` | string type only |
| both | `description` | informational |

- `"object"` and `"array"` field types are refused at load: they cannot
  cross the `AXValue` boundary, so a schema declaring them would promise
  something the engine can never accept.
- **An unknown keyword is a fatal load error.** Silently ignoring one
  would present a constraint as enforced when it is not. That also means a
  keyword can be added in a later manifest version with no
  silently-ignored window.
- `pattern` is deliberately **not** supported. Regex semantics differ
  between languages (Python `re` is not ECMA-262), and the manifest is a
  hashed, cross-language artifact — the same bytes must mean the same
  thing everywhere. A manifest-supplied regex on a fail-closed input path
  is also a ReDoS vector with no timeout mechanism available.
- `integer` accepts an integer and an integral float, because JSON draws
  no int/float distinction on the wire; it rejects a fractional value.
  `number` accepts both and rejects a boolean.
- **Only rules present in the manifest are callable.** A file under
  `rules/` that is not in the manifest does not exist as far as the
  server is concerned.
- On load, the server verifies each referenced file against its declared
  `sha256`; any mismatch is a fatal startup error (no partial serving).
- A rule **source containing a NUL byte** is a fatal load error. The
  `sha256` just verified covers every byte of the file, but the compiler
  receives a NUL-terminated C string and stops at the NUL — so the hash
  would attest to more than what actually compiled.
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

### 7.1 Pre-release gates

One claim this repository makes is **not** currently verified by any automated
run. It does not affect correctness of what is here, and it does not block
merging — but publishing without settling it would ship an untested promise, so
it is written down rather than remembered.

The **Python 3.7 runtime** gate is closed. `python37-verify.yml` runs on a real
CPython 3.7.17 interpreter (Linux x86_64, `ubuntu-22.04` — the newest Linux
runner for which `actions/setup-python` provides 3.7.17): the wheel and the
sdist both install, `pip check` is clean, every shipped module byte-compiles,
the installed package is proven byte-identical to the tested sources, and the
binding suites (`test_validate.py`, `test_binding_lifecycle.py`) plus the
workbench run against it — the workbench through its real Tk GUI path under
Xvfb, calling `Workbench.run_many()` and asserting 100/100 identical decision
hashes. The MCP server is **excluded by design**: the `mcp` SDK's own floor is
3.10+, so only the downlevel refusal (`exit 2`, typed message, no traceback) is
asserted on 3.7. No non-Linux and no non-x86_64 platform is covered.

| Gate | Why it is open | What settles it |
|---|---|---|
| **External PyPI publish result** | The repository gates are closed over the artifact bytes: `pypi-rc-build.yml` builds once, checks metadata/rendering/smoke behavior, and emits an immutable hash-manifested RC; `pypi-publish.yml` only republishes those verified bytes and production requires the matching successful TestPyPI receipt. An actual registry upload, Trusted Publisher configuration, rendered project page, and version availability are external state and have not been exercised by this tree. Separately, `release-guard.yml` runs only on a GitHub `release` event (`published`/`edited`), so it cannot be exercised locally either — `GITHUB_EVENT_PATH` is unset. | Follow `docs/distribution/runbook.md`: configure the documented TestPyPI identity and protected `pypi` environment, dispatch TestPyPI with the RC IDs, inspect/install it, then dispatch production with the same RC IDs and TestPyPI run receipt. |

---

## 8. Out of Scope (v1+)

- **Deterministic routing table**: a declarative, hash-pinned mapping
  from case shape → rule_id, so that rule selection itself becomes an
  auditable engine-side artifact. Deferred to keep v0's surface minimal;
  until then, rule selection stays with the caller (§2.4).

---

## 9. Declared limits

Contract, not heuristics: a call within these bounds is not rejected for
size, and one outside them is rejected with `SRV_FIELDS_TOO_LARGE` (3)
before the engine runs and before anything is logged.

| Bound | Value |
|---|---|
| Fields per call | 64 |
| Field name | 128 bytes (UTF-8) |
| String field value | 4096 bytes (UTF-8), aligned with the engine's own `LIMIT_STRING` |
| `fields`, canonical JSON | 65536 bytes |
| `rule_id` | 128 bytes (UTF-8) |
| Error object, serialized | 256 bytes |

The last row is the one that makes the others hold on the wire. An error
must never be inflated by the input that caused it, and **that bound is in
bytes of the serialized object, not characters of a message**: canonical
JSON is `ensure_ascii`, so one non-ASCII character becomes six, and the
error object travels twice in a single response (escaped inside a text
content block, and again as `structuredContent`). A character cap sees
neither expansion. `error_domain`, `error_code` and `error_name` always
survive truncation, because they are what a client branches on.

The consequence, which `tests/mcp/test_wire_parity.py` measures on the raw
response line: **no tool argument produces a rejection larger than 1 KiB**,
whatever its size or encoding.

The bound is on the **tool result**, and deliberately not on the whole
response. A JSON-RPC envelope also carries the request `id`, which the
protocol requires the server to echo back verbatim and which this server does
not bound: a caller that sends a 1 MiB `id` gets a 1 MiB `id` back. That is
the caller inflating its own response with its own data, not the server
echoing input it rejected, and truncating an `id` would break correlation —
the one thing an `id` is for. Bounding it belongs to a transport-level
request-size limit, which is out of scope here (§4.1) and is the deployment's
job, not the tool contract's.

These bound one call. They are not a rate limit, a queue bound, a timeout,
or a log-size limit; those remain out of scope (§4.1).
