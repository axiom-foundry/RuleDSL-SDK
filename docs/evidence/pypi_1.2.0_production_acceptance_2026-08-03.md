# RuleDSL 1.2.0 production PyPI acceptance evidence

## Scope and result

- Test date: 2026-08-03 (Europe/Istanbul)
- Result: **GO**
- Environment scope: one Windows x86_64 machine, CPython 3.11.9, Tk/Tcl 8.6
- Package under test: the immutable `ruledsl 1.2.0` wheel downloaded from production PyPI
- Engine under test: the hash-verified RuleDSL SDK v1.0.2 Windows x86_64 release bundle

This acceptance run exercised the production wheel's installed Python binding,
the real MCP subprocess/stdio JSON-RPC path, and the real Tk Workbench widget
path. It did not build or import package code from the repository checkout.

The evidence branch starts from repository commit
`9deb467efc81a7909dfa89c54f766dede216a838`. That commit is the base of this
evidence record, **not** the source commit of the published package artifact.
The package artifact source commit is
`837ae3062d666c5e3ef0711966eb8f95605412e5`.

## Production PyPI artifact identity

Registry metadata was read from the production
[`ruledsl 1.2.0` JSON endpoint](https://pypi.org/pypi/ruledsl/1.2.0/json).
The project name and version matched exactly, and the release contained exactly
the following two files with production `files.pythonhosted.org` HTTPS URLs:

| File | Size (bytes) | SHA-256 | Verification |
| --- | ---: | --- | --- |
| `ruledsl-1.2.0-py3-none-any.whl` | 63,790 | `458bc6250fc973369ce68a3b2e90305bf34c88f2e9763001668f5d8eedbc8393` | Registry metadata, frozen expected value, and freshly downloaded bytes all matched |
| `ruledsl-1.2.0.tar.gz` | 60,217 | `6af3c15896a7dd2789b4df162ed4ac222aa90d5aa0d4bdd16bafc46acde91730` | Registry metadata and frozen expected value matched; the sdist was not installed |

The wheel was fetched with cache disabled. Its locally recomputed size and
SHA-256 matched both the registry JSON and the frozen expected values before it
was installed.

## Clean installation and isolation

- Interpreter: CPython 3.11.9, 64-bit
- Resolved MCP SDK: `mcp 2.0.0`
- Installed distribution metadata: Name `ruledsl`, Version `1.2.0`,
  Requires-Python `>=3.7`
- Installed wheel tag: `py3-none-any`
- Packaged MCP surface version: `ruledsl_mcp 0.2.0`
- `pip check`: PASS (`No broken requirements found.`)
- `ruledsl-workbench --help`: PASS
- `ruledsl-mcp --help`: PASS
- `ruledsl-mcp --print-example-rules`: PASS

The clean venv installation used the already verified local wheel as
`<TEMP>/downloads/ruledsl-1.2.0-py3-none-any.whl[mcp]`; pip was permitted to
resolve only MCP and transitive dependencies from production PyPI. The
installed distribution's `direct_url.json` recorded that wheel filename and
the exact SHA-256 above.

Isolation assertions passed:

- CWD was `<TEMP>/neutral`, outside the repository checkout.
- `PYTHONPATH` was unset and the repository root was absent from `sys.path`.
- `ruledsl`, `RuleDSL`, `Bytecode`, `ruledsl.workbench`, `ruledsl_mcp`, and all
  loaded RuleDSL submodules resolved below `<VENV>/Lib/site-packages`.
- Default MCP example rules resolved below
  `<VENV>/Lib/site-packages/ruledsl_mcp/examples/rules`, including its
  `manifest.json`; the checkout fallback was not used.
- The engine DLL came only from the verified v1.0.2 bundle described below.
- The repository checkout was used only to read the existing GUI verification
  reference and to add this evidence document after all acceptance gates
  passed.

## Engine v1.0.2 identity

Assets were downloaded from the production
[`v1.0.2` GitHub Release](https://github.com/axiom-foundry/RuleDSL-SDK/releases/tag/v1.0.2).

| Asset | SHA-256 |
| --- | --- |
| `RuleDSL-SDK-v1.0.2-windows-x86_64.zip` | `75f2f595f3b9e95d0ed3b012c9fcdf2bb1bc1f9d245755436f8c0d9d20ad8f17` |
| `RuleDSL-SDK-v1.0.2-windows-x86_64.SHA256SUMS.txt` | `911640dd9ff7d88e4e98e25ef7ab8ac800cbb981545cf5e6d4bedc24ca904385` |

Both downloaded asset digests matched the frozen values. The checksum asset's
ZIP entry matched the downloaded ZIP. All 67 ZIP entries passed path traversal
checks before extraction. All 62 files listed by `manifests/HASHES.txt` passed
their SHA-256 checks. The required `bin/ruledsl_capi.dll` was present with
SHA-256
`1e8725577c780819adb0aa4f8e669c5b9166840fce7822ca303b157c36a2ac66`.
The library reported `RuleDSL/1.0.2 (abi=1)` at runtime.

## Real MCP stdio acceptance

The installed wheel was invoked from the neutral CWD without `--wrapper`,
without `--rules`, and without `PYTHONPATH`:

```powershell
<VENV>/Scripts/python.exe -m ruledsl_mcp.smoke --engine-lib <ENGINE_DLL>
```

Result: PASS, exit code 0.

- A real server subprocess and stdio JSON-RPC session initialized successfully.
- The exact tool surface was `engine_info`, `evaluate_case`, and `list_rules`.
- Successful evaluation and repeat-record equality checks passed.
- Reserved-field, numeric-string, undeclared-argument, and oversized-input
  typed error checks passed.
- The decision log contained exactly two byte-identical records and matched the
  returned record hash.
- The subprocess shut down cleanly.
- Golden decision hash:
  `e1e99393ea54ee315439861eacb0de7cbfb9410bfb99627f03f7121fb3f921cd`.

## Real Workbench GUI acceptance

A temporary script imported the installed `ruledsl.workbench`, loaded
`<ENGINE_DLL>`, and exercised real Tk widgets. No fake Tk implementation,
widget mocks, or human clicks were used.

Result: PASS, exit code 0.

- Real Tk/Tcl runtime: 8.6/8.6.
- A real `Workbench(engine, dll)` window was constructed and updated.
- The window existed as Tk class `Tk`; its default scenario and rules pane were
  populated.
- `Workbench.RUNS == 100`.
- The real `Workbench.run_many()` handler completed `100/100` runs with an
  identical decision hash and no `NON-DETERMINISTIC` result.
- The result pane contained `decision hash:` and `DECLINE`.
- Workbench decision hash:
  `257fa9413f89b8c3f6aaf9cbc378cc6945a66797aa64aa0969ca6e1a98bef26c`.
- The window was destroyed, then the engine was closed twice to verify
  idempotent close behavior; the process exited cleanly.

## Sanitised command record

Every command below ran with CWD `<TEMP>/neutral` unless it is explicitly a
repository check. Paths have been replaced with `<TEMP>`, `<VENV>`,
`<WHEEL>`, `<BUNDLE>`, and `<ENGINE_DLL>`.

| Purpose | Sanitised command | Exit |
| --- | --- | ---: |
| Repository state | `git status --short --branch` | 0 |
| Local ref identity | `git rev-parse HEAD; git rev-parse main; git rev-parse origin/main` | 0 |
| Live remote identity | `git ls-remote origin refs/heads/main` | 0 |
| No tag at HEAD | `git tag --points-at HEAD` | 0 |
| Python and Tk runtime | `python --version; python -c "import tkinter; ..."` | 0 |
| PyPI metadata | `curl --fail --location --header "Cache-Control: no-cache" https://pypi.org/pypi/ruledsl/1.2.0/json` | 0 |
| Wheel download | `curl --fail --location --header "Cache-Control: no-cache" <PYPI_WHEEL_URL_FROM_JSON> --output <WHEEL>` | 0 |
| PyPI identity checks | `PowerShell: assert exact file set, HTTPS hosts, sizes, registry hashes, and downloaded wheel hash` | 0 |
| Engine downloads | `curl --fail --location <V1.0.2_ASSET_URL> --output <TEMP>/downloads/<ASSET>` | 0 |
| Engine integrity | `PowerShell: verify asset hashes, SHA256SUMS, ZIP paths, layout, and manifests/HASHES.txt` | 0 |
| Venv creation | `python -m venv <VENV>` | 0 |
| Exact wheel install | `<VENV>/Scripts/python.exe -m pip install --no-cache-dir --index-url https://pypi.org/simple "<WHEEL>[mcp]"` | 0 |
| Dependency consistency | `<VENV>/Scripts/python.exe -m pip check` | 0 |
| Metadata/import isolation | `<VENV>/Scripts/python.exe <TEMP>/neutral/verify_install.py` | 0 |
| Workbench CLI | `<VENV>/Scripts/ruledsl-workbench.exe --help` | 0 |
| MCP CLI | `<VENV>/Scripts/ruledsl-mcp.exe --help` | 0 |
| Packaged rules discovery | `<VENV>/Scripts/ruledsl-mcp.exe --print-example-rules` | 0 |
| MCP stdio smoke | `<VENV>/Scripts/python.exe -m ruledsl_mcp.smoke --engine-lib <ENGINE_DLL>` | 0 |
| Real GUI smoke | `<VENV>/Scripts/python.exe <TEMP>/neutral/workbench_gui_acceptance.py` | 0 |

## Limitations and non-goals

- This is evidence from one machine and one Windows x86_64 environment.
- This is not a performance or load test.
- This is not audit-ledger evidence.
- This is not evidence of 24/7 operation or an SLA.
- This is not a formal proof over the complete input space.
- No PyPI or GitHub artifact was uploaded, published, replaced, tagged, or
  released during this acceptance run.
- No environment, package version, release, or workflow was changed.
