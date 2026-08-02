# RuleDSL SDK Release Notes

## Python package 1.2.0 — MCP contract stabilization

*(Draft. Not published; the release itself is a separate decision.)*

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

Two further claims are **not verified by CI** and must be settled before this
version is published, not after (`docs/design/mcp_server_v0.md` §7.1):

- **Python 3.7.** The package declares `requires-python = ">=3.7"`, but every
  CI job runs 3.11; the floor is held by syntax discipline alone. Either run
  the core suites on a real 3.7 interpreter or lower the declared floor.
- **The PyPI publish path.** `pypi-publish.yml` is `workflow_dispatch` only —
  it never runs on push or pull request, so its wheel smoke test has not run
  against this tree. It also does not verify that the wheel version matches a
  tag, that `README-pypi.md` renders on PyPI, or that the version is not
  already uploaded. `release-guard.yml` runs only on a GitHub `release` event
  and so cannot be exercised locally either. Publish to TestPyPI and install
  from it first.

Until then, the published package remains `1.1.1`; `1.2.0` exists only in
source. The repository README says so explicitly rather than showing a version
nobody can install.

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