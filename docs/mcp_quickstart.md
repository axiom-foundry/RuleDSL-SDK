# RuleDSL MCP Server v0 — Quickstart

Status: **EXPERIMENTAL** — not part of the release contract surface; no
ABI or compatibility promise; may change or be withdrawn without a major
engine version bump. Design contract: `docs/design/mcp_server_v0.md`.

Version pairing: **`ruledsl` 1.1.x pairs with engine bundle v1.0.2** — the
latest release. The Python package is pure Python; the engine binary is
never inside it.

> **"The agent invokes; the engine decides."** The MCP server is a thin,
> deterministic invocation boundary — the AI client picks which declared
> rule runs on which explicit input; every decision is produced by the
> engine and logged as a canonical, replayable record.

---

## 1. Prerequisites

- **Python 3.10+** with a **virtual environment**. Use a venv rather than
  the system Python: the `mcp` package pulls a modern dependency set
  (pydantic, starlette, …) that is known to conflict with Debian/Ubuntu
  distro-managed packages. (On an older interpreter, `ruledsl-mcp` exits
  with a clear message — the base `ruledsl` package still works on 3.7+.)

  ```bash
  python3 -m venv .venv
  . .venv/bin/activate          # Windows: .venv\Scripts\activate
  pip install "ruledsl[mcp]"
  ```

  The `[mcp]` extra installs the `ruledsl` package (engine wrapper +
  workbench) together with the `ruledsl_mcp` server and its only
  third-party dependency, the official `mcp` SDK. It also provides the
  `ruledsl-mcp` console command. **No repository checkout is needed on
  this route** — an example rule library ships inside the package.

  **Dev checkout alternative** (no pip): everything lives in this one
  repository — point `PYTHONPATH` at `bindings/python` (which provides
  both `ruledsl` and `ruledsl_mcp`) and `pip install mcp` into the venv.

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
  files it declares. The package ships a ready example — print its
  location with `ruledsl-mcp --print-example-rules` (an information-only
  helper: `--rules` itself always stays explicit). On a checkout, the
  same example lives at `rules/`.

---

## 2. Running the server

All three flags are **required and explicit** — the server never chooses
a rules directory, log file, or engine library on its own (explicit-input
policy; the same reason `now_utc_ms` is a mandatory parameter):

```bash
# Linux/macOS
ruledsl-mcp \
    --rules "$(ruledsl-mcp --print-example-rules)" \
    --decision-log /path/to/decisions.jsonl \
    --engine-lib /path/to/bundle/bin/libruledsl_capi.so
```

```powershell
# Windows (PowerShell, inside the activated venv)
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install "ruledsl[mcp]"
ruledsl-mcp `
    --rules "$(ruledsl-mcp --print-example-rules)" `
    --decision-log C:\path\to\decisions.jsonl `
    --engine-lib C:\path\to\bundle\bin\ruledsl_capi.dll
```

**What success looks like:** the server prints *nothing* — it speaks MCP
over **stdio** and waits for a client (Claude Desktop, an agent runtime,
or the smoke client below) to spawn and drive it. It is not used
interactively. To see it work end to end right now, run the smoke client
(§5): ten `ok` lines and a `PASS decision_hash=…`.

On the dev-checkout route the equivalent is
`python -m ruledsl_mcp.server` (module form — the package uses relative
imports, so invoking `server.py` as a bare script will fail) with
`PYTHONPATH` set to `<RuleDSL-SDK>/bindings/python`.

---

## 3. Claude Desktop configuration

Add to `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "ruledsl": {
      "command": "/path/to/.venv/bin/ruledsl-mcp",
      "args": [
        "--rules", "/path/to/example/rules",
        "--decision-log", "/path/to/decisions.jsonl",
        "--engine-lib", "/path/to/libruledsl_capi.so"
      ]
    }
  }
}
```

For the `--rules` value, paste the output of
`ruledsl-mcp --print-example-rules` (or your own library's path).
On Windows, `command` is `...\\.venv\\Scripts\\ruledsl-mcp.exe`.

For a dev checkout (no pip): set `command` to the venv's `python`,
prepend `"-m", "ruledsl_mcp.server"` to `args`, and add an `env` entry
setting `PYTHONPATH` to `/path/to/RuleDSL-SDK/bindings/python`.

---

## 4. What a real session looks like

Not a mock-up: the transcript below is from a live verification run — an
AI agent driving the server over real MCP JSON-RPC/stdio, against a
v1.0.2 engine taken from a hash-verified release bundle:

```
[handshake ok]   server=ruledsl-mcp | protocol=2024-11-05
[tools/list ok]  ['engine_info', 'evaluate_case', 'list_rules']   <- exactly 3, closed list
[engine_info ok] engine=1.0.2 abi=1 schema=mcp_decision_record_v0 (read at runtime, no drift)
[list_rules ok]  ['allow_small', 'block_extreme', 'velocity_limits']
[evaluate #1 ok] DECLINE - block_extreme - hash=e1e99393ea54ee31...
[evaluate #2 ok] record-identical=True
[reserved ok]    server/2/SRV_RESERVED_FIELD  (rejected before reaching the engine)
[decision-log]   2 lines, byte-identical=True, canonical JSONL
```

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
python -m ruledsl_mcp.smoke --engine-lib /path/to/libruledsl_capi.so
```

That is the whole command on the pip route: `--rules` defaults to the
packaged example library and the installed `ruledsl` wrapper is used
automatically (`--wrapper` exists for bare-checkout runs; the historical
`Tools/mcp_demo/smoke_client.py` entry point still works from a checkout
and simply delegates here). CI runs both routes on every PR
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
| server exits at startup: sha256 mismatch | a rule file does not match its manifest hash — fatal by design, no partial serving | restore the file or update the manifest deliberately |
| server exits at startup: `manifest_version` missing/unknown | manifest format not recognized — the server never guesses | use `"manifest_version": 1` |
| `ruledsl-mcp` exits: "requires Python 3.10+" | the `[mcp]` extra needs 3.10+ (the `mcp` SDK's floor); the base package works on 3.7+ | create the venv with a newer interpreter |
| `ModuleNotFoundError: ruledsl` or `ruledsl_mcp` | package not installed (or, on the dev-checkout route, `PYTHONPATH` not set) | `pip install "ruledsl[mcp]"`, or point `PYTHONPATH` at `<RuleDSL-SDK>/bindings/python` |
| `ModuleNotFoundError: mcp` | base package installed without the extra | `pip install "ruledsl[mcp]"` (or `pip install mcp`) |
| `attempted relative import` | server started as a bare script | use `ruledsl-mcp` or `python -m ruledsl_mcp.server` |
