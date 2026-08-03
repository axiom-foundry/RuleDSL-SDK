# RuleDSL SDK Release Notes

## Python package 1.2.0 — MCP contract stabilization

*Published to PyPI on 2026-08-03 from source commit
`837ae3062d666c5e3ef0711966eb8f95605412e5`. No tag or GitHub Release was
created for this Python-package publication.*

This is Python package 1.2.0 with MCP package surface 0.2.0.

One piece of work, not a run of small fixes: the MCP surface and the language
bindings now refuse the inputs they used to accept quietly, and CI holds them
to it.

The engine is unchanged — same `v1.0.2` binary, same `v0.9` language, same
published golden decision hash `e1e99393…21cd`. What changed is everything
around it: what reaches the engine, and what a caller is told when something
does not.

### Why

Shipped v0.9 compares across types silently and applies no static type
checking (`docs/language/conformance_status_v0_9.md`). That is documented and
deliberate, but it has a consequence at the boundary: an unvalidated `"2000"`
does not *fail*. It matches no threshold and falls through to whatever rule
catches everything — a wrong decision that looks exactly like a right one. The
engine was deterministic and correct throughout; nothing was checking its
input. Several defects in this release share that shape.

### Strict per-rule input schemas

`rules/manifest.json` moves to `manifest_version: 2`, and every rule must now
declare an `input_schema`: the fields it accepts, their types, whether they are
required, and simple bounds. `evaluate_case` enforces it before the engine
runs and before anything is logged.

The schemas live in the manifest because the manifest is already hashed and
its `manifest_sha256` is reported by `engine_info` — so the input contracts
become tamper-evident with nothing new to verify. An unknown schema keyword is
a fatal startup error rather than a silent no-op: a constraint that looks
enforced but is not is worse than no constraint.

### Typed errors, and failures that report as failures

Failed calls now return `isError: true` with a stable error object in both
`structuredContent` and text. Previously unknown-rule, reserved-field and
engine errors all came back as *successful* calls carrying an error-shaped
payload — an orchestrator checking only transport success counted them as
decisions.

The error object gains a fifth key, `field`, naming what was rejected
(`"fields.amount"`, `"now_utc_ms"`), so an agent can correct itself without
parsing prose. Server-domain codes 3–9 join the existing 1–2 for conditions
the engine cannot see: oversized input, unsafe values, invalid field names,
schema violations, a non-integer clock, internal invariants, and undeclared
arguments.

### Binding parity: what the engine sees is what you sent

Both the Python and C# bindings now refuse values that would cross the
engine's value boundary altered, rather than passing a changed version
through:

- a string containing NUL — the engine gets a NUL-terminated C string and
  would see only the prefix;
- an integer beyond ±(2^53−1) — binary64 rounds it, so the engine would
  evaluate a different number;
- a non-finite float, reported as `AX_ERR_NON_FINITE`;
- a rule *source* containing NUL, where the file hash would otherwise attest
  to more than what compiled.

Both bindings also close a lifetime hole: `close()` / `Dispose()` now waits
for in-flight native calls instead of freeing the compiler underneath one.
That failure was not loud — it surfaced as a "successful" decision with
silently empty output fields.

### CI that holds the line

- A new `csharp-verify` workflow: the C# binding had **no** CI coverage at
  all, and its concurrency defects are precisely the kind review does not
  catch.
- Engine-free validation tests run before the engine download, so the
  cheapest failures surface first.
- The handler suite additionally runs under `python -O`, because a
  correctness check written as `assert` disappears there.
- The MCP SDK is verified at an exact version **with its transitive closure
  pinned** (`Tools/ci/constraints-mcp-2.0.0.txt`). Pinning `mcp` alone would
  not be reproducible: argument-model construction and lax-mode coercion live
  in pydantic, which could move under an unchanged `mcp` version. The package
  declares `>=2.0,<3`, but that range is *permission, not evidence* — only the
  versions in the CI matrix are tested, which today is `2.0.0`, the whole 2.x
  line so far.
- The C# suite builds **and runs** on `net6.0` and `net8.0`, so ".NET 6+" is a
  tested claim. The previous ".NET Framework 4.7.2+" claim was false — the
  binding uses `Marshal.PtrToStringUTF8` and nullable reference types, neither
  of which exists there.
- A new `test_wire_parity` suite drives a **real JSON-RPC/stdio session**
  against a subprocess server. In-process calls skip the SDK's argument
  pre-parsing, so a defect living between the wire and the handler is
  invisible to them — which is how a JSON-encoded `fields` string was accepted
  and logged as a decision.

### Breaking changes

Deliberate, and taken in one step. The MCP and manifest surfaces are
explicitly EXPERIMENTAL with no compatibility promise
(`docs/design/mcp_server_v0.md` §7); carrying compatibility debt for unsafe
paths would cost more than breaking them now.

| Change | Why |
|---|---|
| `manifest_version` 1 is refused | v1 has no `input_schema`; accepting it keeps the unvalidated path alive under a "supported" banner |
| Failures return `isError: true` | a failure reported as success is the defect |
| `now_utc_ms` must be a JSON integer | a numeric string was silently coerced; an int silently became a float, so the same evaluation logged differently over the wire than in process |
| Undeclared call arguments are rejected | they were silently dropped, so a misspelled `now_utc_ms` read as absent |
| `list_rules` output gains `input_schema` | it is the only way a caller can construct an acceptable call |
| MCP SDK 1.x / FastMCP support removed | it could not produce a single failure shape; supporting both meant two error contracts |
| Decision record schema is `mcp_decision_record_v1` | `now_utc_ms` is always an integer and field values are guaranteed exactly representable |
| A JSON-encoded `fields` string is refused | the SDK pre-parsed it into an object before validation ran, so a string argument produced a real decision |
| `now_utc_ms` must be at or after the epoch | the advertised schema declares `minimum: 0`; honouring a wider range than the published one is the same defect as publishing one the server does not honour |
| `now_utc_ms` may be supplied as an argument **or** as a field, never both | the argument used to overwrite the field silently, so the caller's value did not apply |
| Text with no UTF-8 form (a lone surrogate) is refused in both bindings | C# substituted U+FFFD silently and Python raised an untyped `UnicodeEncodeError`; the engine would have evaluated a character the caller never sent |

**One break reaches beyond the experimental surface.** The Python and C#
bindings now raise on an integer beyond ±(2^53−1) where they previously passed
a silently rounded double. Code that sends a large identifier — an account
number or ledger id — as an integer field will start seeing an error. That is
the point: the engine was already evaluating a different number. **Pass
identifiers as strings**, which is the correct type for them regardless.

### What this release does NOT claim

The MCP decision log is a decision *record*, not an audit ledger. It
guarantees that a successfully written record's `fields` and `now_utc_ms` are
exactly what the engine evaluated. It does not provide atomicity or ordering
between concurrent writers, `fsync` durability, caller identity, a
whole-record hash or chain, entries for failed calls, PII redaction, or
rotation. Those remain open and are separate work — see
`docs/design/mcp_server_v0.md` §4.1.

The **Python 3.7 floor is now verified by CI** (`python37-verify.yml`), on a
real CPython 3.7.17 interpreter on Linux x86_64: wheel and sdist install, every
shipped module byte-compiles, and the binding and workbench suites run there —
the workbench through its actual GUI path. The MCP server is excluded: the
`mcp` SDK requires Python 3.10+, so only its downlevel refusal is checked on
3.7. Nothing outside Linux x86_64 is covered.

### Publication evidence

The external PyPI publish gate closed on 2026-08-03 with one immutable artifact
chain:

- RC workflow run `30834024674`, artifact `8864078716`, source
  `837ae3062d666c5e3ef0711966eb8f95605412e5`, tree
  `dced7670cd80107cf320a5aa5734106f41960f99`;
- TestPyPI workflow run `30838714829`, post-registry receipt artifact
  `8866047202`, receipt JSON SHA-256
  `215faaa10b1c0e54042e4612dde17a1d7e3453f3287e2ef6a87768e46758fd71`;
- production workflow run `30841726760`, published at
  <https://pypi.org/project/ruledsl/1.2.0/>.

Production contains exactly one wheel and one sdist. Their registry and
downloaded SHA-256 values match the RC and TestPyPI bytes:

- `ruledsl-1.2.0-py3-none-any.whl`:
  `458bc6250fc973369ce68a3b2e90305bf34c88f2e9763001668f5d8eedbc8393`;
- `ruledsl-1.2.0.tar.gz`:
  `6af3c15896a7dd2789b4df162ed4ac222aa90d5aa0d4bdd16bafc46acde91730`.

The production README render and clean-venv install/smoke checks passed. The
upload used Trusted Publishing behind the required-reviewer environment gate.
This publication did not create a tag or GitHub Release, and it did not change
the engine: the binary bundle remains v1.0.2 and the language implementation
remains v0.9.

---

## What is included

- Public SDK headers (`include/`)
- Compiled engine and compiler binaries (`bin/`)
- Public operational and language docs (`docs/`)
- Example programs and rule files (`examples/`)
- Deterministic delivery manifests (`manifests/`)

## What is not included

- Engine source code
- Compiler source code
- Debug build artifacts and private tooling

## Supported platforms

See the current distribution packet and `docs/compatibility_matrix.md`.

## Upgrade / Compatibility

Use this boilerplate for each release:

```text
This release follows the compatibility matrix published in docs/compatibility_matrix.md.
Compile rules with the provided ruledslc version and run ruledslc verify on each bytecode artifact.
Before evaluation, call ax_check_bytecode_compatibility and proceed only when status is OK.
```

## Verification instructions

1. Validate `manifests/HASHES.txt` before running binaries.
2. Confirm `ruledslc --version` matches release metadata.
3. Run the compile -> verify -> evaluate smoke path.

## Known limitations

- Signature verification policy may differ by distribution tier.
- Evaluation bundles ship the PolyForm Free Trial License (`LICENSE`); `manifests/LICENSE_STATUS.txt` reports `LICENSE=PolyForm-Free-Trial-1.0.0` / `TYPE=EVALUATION`.
