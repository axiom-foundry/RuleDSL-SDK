# RuleDSL Compiler Contract (`ruledslc`)

## Purpose

`ruledslc` compiles RuleDSL source (`.rule`) into deterministic RuleDSL bytecode (`.axbc`).
The compiler is distributed as a licensed binary for local customer use.

## Stable CLI Surface (MVP)

```text
ruledslc compile <input.rule> -o <output.axbc> [--lang 0.9] [--target axbc3] [--emit-manifest <path.json>]
ruledslc verify <input.axbc>
ruledslc license --status
ruledslc --version
ruledslc --help
```

## Stable Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `2` | CLI usage error |
| `3` | Compile error (syntax or semantic) |
| `4` | Incompatible language/target request |
| `5` | Internal compiler failure |
| `6` | Structurally invalid bytecode (`verify`) |
| `7` | Unsupported bytecode/language/ABI version (`verify`) |
| `8` | Corrupted bytecode payload (`verify`) |

## `verify` Contract

`ruledslc verify <input.axbc>` performs deterministic offline checks:
- bytecode header structure,
- supported AXBC schema version,
- supported language version,
- minimum engine ABI compatibility,
- payload integrity check.

Successful output is machine-readable:

```text
STATUS=OK
AXBC=3
LANG=0.9
ABI=1
FLAGS=0
```

Failure output is machine-readable and reason-coded, for example:

```text
STATUS=INCOMPATIBLE
REASON=UNSUPPORTED_AXBC
```

## License Status Command

`ruledslc license --status` is deterministic and offline.
Current baseline is a local non-network status surface (no telemetry, no SaaS dependency).

## Determinism Contract

For the same compiler version, same input bytes, and same compile flags, `ruledslc` MUST produce byte-identical `.axbc` output.

`ruledslc` output and manifest generation MUST NOT include:
- timestamps,
- random salts,
- host-specific absolute paths.

## Version Handshake

`ruledslc --version` returns machine-readable metadata:

```text
RuleDSL/1.0.0 (lang=0.9; axbc=3; abi=1)
BUILD_HASH=<short-hash>
```

## Compatibility Policy

| Compiler | Language | Bytecode target | SDK ABI | Minimum engine version |
| --- | --- | --- | --- | --- |
| `1.0.x` | `0.9` | `axbc3` | `1` | `1.0.0` |

Compatibility rules:
- Compiler major version change MAY introduce breaking compile behavior.
- Compiler minor/patch updates SHOULD keep language compatibility within the same major line.
- Engine MUST reject incompatible bytecode schema or ABI requirements before evaluation.

## Optional Compile Manifest

`--emit-manifest <path.json>` writes deterministic compile metadata:

- `compiler_version`
- `language_version`
- `target`
- `input_sha256`
- `output_sha256`
- `compile_flags`

The manifest omits timestamps by default.

## Security and Distribution

- The compiler is distributed as a licensed binary.
- Compilation runs locally in customer environments.
- No SaaS compiler dependency is required.