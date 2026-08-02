# RuleDSL MCP Server v0 — Quickstart

Status: **EXPERIMENTAL** — not part of the release contract surface; no
ABI or compatibility promise; may change or be withdrawn without a major
engine version bump. Design contract: `docs/design/mcp_server_v0.md`.

Version pairing: **engine bundle v1.0.2**. The Python package is pure Python;
the engine binary is never inside it.

> ⚠️ **This document describes the `1.2.0` contract, which is a source
> candidate — it is not on PyPI yet.** `pip install "ruledsl[mcp]"` today
> installs **1.1.1**, which implements the *previous* contract: rule libraries
> use `manifest_version: 1` and declare no `input_schema`, failures come back
> as ordinary successful results instead of `isError`, and `now_utc_ms` is
> coerced rather than checked. Following the instructions below against 1.1.1
> will not work — a v2 manifest is not something 1.1.1 understands.
>
> Until `1.2.0` is published, run this server from a checkout of the repository
> at the matching commit. The version split is deliberate and is stated the
> same way in the repository README.

> **"The agent invokes; the engine decides."** The MCP server is a thin,
> deterministic invocation boundary — the AI client picks which declared
> rule runs on which explicit input; every decision is produced by the
> engine and logged as a canonical, replayable record.

---

## 1. Prerequisites

- **Python 3.10+** with a **virtual environment**. Use a venv rather than
  the system Python: the `mcp` package pulls a modern dependency set
  (pydantic, starlette, …) that is known to conflict with Debian/Ubuntu
  distro-managed packages.

  The two floors differ, on purpose:

  | | Python | Why |
  |---|---|---|
  | `ruledsl` (binding + workbench) | **3.7+** | pure `ctypes`, no dependencies |
  | `ruledsl[mcp]` (this server) | **3.10+** | the `mcp` SDK's own floor |

  Package metadata can only state one floor, so the MCP requirement is
  enforced at startup instead: on an older interpreter `ruledsl-mcp` exits
  with a clear message rather than an import-time stack trace. The MCP SDK
  is required as `mcp>=2.0,<3`. That range is permission, not evidence: CI
  verifies exactly the versions in its matrix, pinned together with their
  transitive dependencies (`Tools/ci/constraints-mcp-<version>.txt`). Today
  that is `mcp==2.0.0`, which happens to be the entire 2.x line so far.

  **Install from a checkout — the route that works today.** The version on
  PyPI is `1.1.1`, which implements the previous contract, so `pip install
  "ruledsl[mcp]"` does not give you the server this document describes.
  Everything lives in this one repository: put `bindings/python` on
  `PYTHONPATH` (it provides both `ruledsl` and `ruledsl_mcp`) and install
  only the MCP SDK.

  ```bash
  # Linux/macOS
  git clone https://github.com/axiom-foundry/RuleDSL-SDK.git
  cd RuleDSL-SDK
  python3 -m venv .venv
  . .venv/bin/activate
  pip install "mcp>=2.0,<3"
  export PYTHONPATH="$PWD/bindings/python"
  ```

  ```powershell
  # Windows (PowerShell)
  git clone https://github.com/axiom-foundry/RuleDSL-SDK.git
  cd RuleDSL-SDK
  py -3.11 -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install "mcp>=2.0,<3"
  $env:PYTHONPATH = "$PWD\bindings\python"
  ```

  The rule library is then `rules/` in the checkout, and the server is
  `python -m ruledsl_mcp.server`.

  **Install from PyPI — after `1.2.0` is published.** The `[mcp]` extra
  installs the `ruledsl` package (engine wrapper + workbench) together with
  the `ruledsl_mcp` server, its only third-party dependency (the official
  `mcp` SDK), and the `ruledsl-mcp` console command; an example rule library
  ships inside the wheel, so no checkout is needed. Do **not** use this route
  yet — it currently installs `1.1.1`:

  ```bash
  # Only once 1.2.0 is on PyPI. Check first: pip index versions ruledsl
  pip install "ruledsl[mcp]"
  ```

- **The engine library** (`ruledsl_capi.dll` on Windows,
  `libruledsl_capi.so` on Linux) from a **release bundle**: download
  `RuleDSL-SDK-v1.0.2` for your platform and verify hashes first —
  `SHA256SUMS.txt` is authoritative (see `docs/distribution.md`):

  ```bash
  # Linux
  sha256sum --ignore-missing -c RuleDSL-SDK-v1.0.2-linux-x86_64.SHA256SUMS.txt
  ```

  ```powershell
  # Windows (PowerShell): compute, then compare against the .SHA256SUMS.txt value
  Get-FileHash .\RuleDSL-SDK-v1.0.2-windows-x86_64.zip -Algorithm SHA256
  Get-Content .\RuleDSL-SDK-v1.0.2-windows-x86_64.SHA256SUMS.txt
  ```

  Then use the library from the bundle's `bin/`.

- **A rule library**: a directory holding `manifest.json` plus the rule
  files it declares. On a checkout it is `rules/`. (Once `1.2.0` is
  published, the same example also ships inside the wheel; print its
  location with `ruledsl-mcp --print-example-rules`, an information-only
  helper — `--rules` itself always stays explicit.)

---

## 2. Running the server

All three flags are **required and explicit** — the server never chooses
a rules directory, log file, or engine library on its own (explicit-input
policy; the same reason `now_utc_ms` is a mandatory parameter):

```bash
# Linux/macOS - from the checkout, with PYTHONPATH set as in section 1
python -m ruledsl_mcp.server \
    --rules ./rules \
    --decision-log /path/to/decisions.jsonl \
    --engine-lib /path/to/bundle/bin/libruledsl_capi.so
```

```powershell
# Windows (PowerShell) - from the checkout, inside the activated venv
python -m ruledsl_mcp.server `
    --rules .\rules `
    --decision-log C:\path\to\decisions.jsonl `
    --engine-lib C:\path\to\bundle\bin\ruledsl_capi.dll
```

Once `1.2.0` is on PyPI the same invocation is available as the
`ruledsl-mcp` console command, with
`--rules "$(ruledsl-mcp --print-example-rules)"` in place of `./rules`.
Until then that command belongs to `1.1.1` and speaks the old contract.

**What success looks like:** the server prints *nothing* — it speaks MCP
over **stdio** and waits for a client (Claude Desktop, an agent runtime,
or the smoke client below) to spawn and drive it. It is not used
interactively. To see it work end to end right now, run the smoke client
(§5): a series of `ok` lines and a `PASS decision_hash=…`.

Note the module form: the package uses relative imports, so invoking
`server.py` as a bare script will fail.

---

## 3. Claude Desktop configuration

Add to `claude_desktop_config.json` (Settings → Developer → Edit Config):

From a checkout — the route that works today:

```json
{
  "mcpServers": {
    "ruledsl": {
      "command": "/path/to/.venv/bin/python",
      "args": [
        "-m", "ruledsl_mcp.server",
        "--rules", "/path/to/RuleDSL-SDK/rules",
        "--decision-log", "/path/to/decisions.jsonl",
        "--engine-lib", "/path/to/libruledsl_capi.so"
      ],
      "env": { "PYTHONPATH": "/path/to/RuleDSL-SDK/bindings/python" }
    }
  }
}
```

On Windows, `command` is `...\\.venv\\Scripts\\python.exe` and the paths use
backslashes (escaped in JSON).

Once `1.2.0` is on PyPI, the console command replaces all of that: set
`command` to `/path/to/.venv/bin/ruledsl-mcp`
(`...\\.venv\\Scripts\\ruledsl-mcp.exe` on Windows), drop the `-m` argument
and the `env` block, and paste the output of
`ruledsl-mcp --print-example-rules` as `--rules`.

---

## 4. What a real session looks like

Not a mock-up: the transcript below is from a live verification run — an
AI agent driving the server over real MCP JSON-RPC/stdio, against a
v1.0.2 engine taken from a hash-verified release bundle:

```
[handshake ok]   server=ruledsl-mcp | protocol=2024-11-05
[tools/list ok]  ['engine_info', 'evaluate_case', 'list_rules']   <- exactly 3, closed list
[engine_info ok] engine=1.0.2 abi=1 schema=mcp_decision_record_v1 (read at runtime, no drift)
[list_rules ok]  ['allow_small', 'block_extreme', 'velocity_limits'] + each rule's input_schema
[evaluate #1 ok] DECLINE - block_extreme - hash=e1e99393ea54ee31...
[evaluate #2 ok] record-identical=True
[reserved ok]    isError=true server/2/SRV_RESERVED_FIELD  field=fields.now_utc_ms
[typed ok]       isError=true server/6/SRV_SCHEMA_VIOLATION field=fields.amount
                 (amount was the STRING "30000" - refused, not evaluated)
[decision-log]   2 lines, byte-identical=True, canonical JSONL
```

Note the second rejection. `"30000"` is not a rounding problem: the shipped
v0.9 engine compares across types silently, so an unvalidated string matches
no threshold and falls through to whatever rule catches everything — a wrong
decision that looks like a normal one. It never reaches the engine now, and
nothing is written to the log.

The same scenario (`block_extreme`, `{"amount": 30000.0}`,
`now_utc_ms=1700000000000`) produces decision_hash
`e1e99393ea54ee315439861eacb0de7cbfb9410bfb99627f03f7121fb3f921cd`
on a Windows local build and on a Linux downloaded release engine — and
matches the hash produced by the GUI workbench for the same case. Three
surfaces (GUI, MCP, replay tooling), one set of bytes.

---

## 5. E2E smoke client

The package carries a dependency-free (stdlib-only) JSON-RPC/stdio client
that spawns the real server and asserts the v0 contract: handshake,
closed 3-tool list, byte-identical decision records for identical calls,
and the reserved-field rejection. Exit code 0 = PASS.

```bash
# From the checkout, with PYTHONPATH set as in section 1
python -m ruledsl_mcp.smoke \
    --engine-lib /path/to/libruledsl_capi.so \
    --rules ./rules
```

`Tools/mcp_demo/smoke_client.py` is the historical entry point and still
works from a checkout; it simply delegates here. Once `1.2.0` is on PyPI,
`--rules` and `--wrapper` can both be omitted: the packaged example library
and the installed `ruledsl` wrapper are then found automatically. CI runs both routes on every PR
(`verify-mcp-python` job) against the shipped release engine — downloaded
from Releases and hash-verified first — so the transport path is covered
end to end against the same binaries users run, not just at handler
level, and the packaged example library is byte-compared against the
repository's canonical `rules/` so the two can never drift.

---

## 6. Troubleshooting

| Symptom | Meaning | Fix |
|---|---|---|
| server starts and prints nothing | expected — MCP servers are silent on stdio until a client connects (§2) | verify with `python -m ruledsl_mcp.smoke` |
| error `engine/4 AX_ERR_MISSING_NOW_UTC_MS` | `now_utc_ms` omitted — it is always required, even for rules that never read the clock | pass explicit epoch milliseconds |
| error `server/2 SRV_RESERVED_FIELD` | `fields` contains the key `now_utc_ms` | remove it from `fields`; the clock travels only as the top-level parameter |
| error `server/1 SRV_UNKNOWN_RULE_ID` | rule id not in the manifest (files on disk are invisible unless declared) | check `list_rules`; add the rule to the manifest |
| error `server/3 SRV_FIELDS_TOO_LARGE` | a declared bound exceeded: >64 fields, >128-byte name, >4 KiB string, >64 KiB total, or a `rule_id` over 128 bytes | send the case the rule actually needs |
| error `server/4 SRV_UNSAFE_FIELD_VALUE` | a value the engine cannot receive faithfully: NUL in a string, an integer beyond ±(2^53−1), text with no UTF-8 form (a lone surrogate), or a nested object/array | pass identifiers as strings; flatten the case |
| error `server/5 SRV_FIELD_NAME_INVALID` | a field name that is empty, not a string, or contains NUL | fix the key |
| error `server/6 SRV_SCHEMA_VIOLATION` | `fields` does not match the rule's `input_schema` — wrong type, undeclared key, missing required key, or a bound violated | call `list_rules` and satisfy that rule's schema; `field` in the error names the offender |
| error `server/7 SRV_NOW_UTC_MS_NOT_INTEGER` | `now_utc_ms` is numeric but not a valid whole millisecond: fractional, beyond 2^53−1, or negative | send whole epoch milliseconds at or after 1970. `1700000000000.0` is accepted and normalized to the integer `1700000000000`, so both spellings log the same record |
| error `server/8 SRV_INTERNAL` | a server invariant was violated — not your input | report it; the message names the invariant |
| error `server/9 SRV_UNKNOWN_ARGUMENT` | an argument the tool does not declare (often a typo) | check the spelling against the tool's `inputSchema` |
| error `engine/5 AX_ERR_NOW_UTC_MS_NOT_NUMBER` | `now_utc_ms` sent as a string | send a JSON integer; it is never coerced |
| error `engine/1 AX_ERR_INVALID_ARGUMENT`, `field: "fields"` | `fields` sent as a JSON-encoded **string** instead of an object. Some clients do this by habit; the transport SDK would parse it back into an object, so the server checks the raw argument first | send a real JSON object |
| error `engine/1 AX_ERR_INVALID_ARGUMENT`, `field: "rule_id"` | `rule_id` missing, empty, or not a string | send a rule id from `list_rules` |
| server exits at startup: sha256 mismatch | a rule file does not match its manifest hash — fatal by design, no partial serving | restore the file or update the manifest deliberately |
| server exits at startup: `manifest_version` missing/unknown | manifest format not recognized — the server never guesses | use `"manifest_version": 2` (v1 is refused: it has no `input_schema`) |
| server exits at startup: rule entry must declare … `input_schema` | manifest v2 requires an input contract per rule | see §7 |
| server exits at startup: unsupported keyword in `input_schema` | an unknown keyword is fatal, never ignored — otherwise a constraint would look enforced when it is not | use only the keywords in §7 |
| server exits: "requires Python 3.10+" | the MCP server needs 3.10+ (the `mcp` SDK's floor); the base binding works on 3.7+ | create the venv with a newer interpreter |
| `ModuleNotFoundError: ruledsl` or `ruledsl_mcp` | `PYTHONPATH` does not point at the checkout's `bindings/python` | `export PYTHONPATH=<RuleDSL-SDK>/bindings/python` (after `1.2.0` is published, `pip install "ruledsl[mcp]"` instead) |
| `ModuleNotFoundError: mcp` | the MCP SDK is not in this venv | `pip install "mcp>=2.0,<3"` |
| `attempted relative import` | server started as a bare script | use `python -m ruledsl_mcp.server` |
| `manifest_version` refused, or `isError` never appears | you are running the published `1.1.1`, which speaks the previous contract | run from a checkout until `1.2.0` is published (see §1) |

---

## 7. Declaring a rule's input schema

Every rule in `manifest.json` must declare the shape of the case it accepts.
This is the step that did not exist before, and it is the one that stops a
type mistake from becoming a wrong decision.

```json
{
  "manifest_version": 2,
  "rules": {
    "allow_small": {
      "file": "allow_small.ruledsl.txt",
      "sha256": "55652608…",
      "version": "1.0.0",
      "input_schema": {
        "type": "object",
        "additionalProperties": false,
        "required": ["amount"],
        "properties": {
          "amount": {"type": "number", "minimum": 0}
        }
      }
    }
  }
}
```

Declare **every field the rule reads**, and mark it `required`. A field a
rule references but the case omits is a runtime error deep inside the
engine; declared required, it is a clear rejection naming the field before
anything runs.

Supported keywords:

| Where | Keyword | Notes |
|---|---|---|
| root | `type` | required, must be `"object"` |
| root | `properties` | required |
| root | `required` | array of names that appear in `properties` |
| root | `additionalProperties` | absent or `false`; the closed world is the contract |
| field | `type` | **required**: `number`, `integer`, `string`, `boolean`, `null`, or a list |
| field | `enum` | non-empty array of allowed scalars |
| field | `minimum` / `maximum` | numeric fields only |
| field | `minLength` / `maxLength` | string fields only |
| both | `description` | informational |

Three rules that are easy to trip over:

- **An unknown keyword is a fatal startup error.** `pattern`, `format`,
  `nullable` and friends are not silently ignored — a constraint that looks
  enforced but is not is worse than no constraint. (`pattern` is excluded
  deliberately: regex semantics differ between languages, and the manifest
  is a hashed cross-language artifact.)
- **`object` and `array` field types are refused.** They cannot cross the
  engine's value boundary, so a schema promising them would promise
  something the engine can never accept.
- **`integer` accepts `2000` and `2000.0`, rejects `2000.5`.** JSON draws no
  int/float distinction on the wire. `number` accepts both and rejects
  `true` — a boolean is not a number here.

Because the manifest is hashed and `engine_info` reports its
`manifest_sha256`, these schemas are tamper-evident for free: there is no
second artifact to verify.

---

## 8. What the decision log is, and is not

`--decision-log` writes one canonical JSON line per successful evaluation.

**It guarantees:** the `fields` and `now_utc_ms` in a written record are
exactly what the engine evaluated. Values that would reach the engine
altered are refused before evaluation, so a record cannot describe an input
other than the one that produced the decision.

**It is not an audit ledger.** There is no writer lock or sequence number
(so concurrent writers can interleave and their order cannot be
reconstructed afterwards), no `fsync` (a crash can leave a partial line), no
request id, principal or tenant, no hash over the whole record and no chain
between records, no entry for failed calls, no PII redaction, and no size or
rotation limit. Treat the file as evidence *of a decision*, not as a system
of record. See `docs/design/mcp_server_v0.md` §4.1.
