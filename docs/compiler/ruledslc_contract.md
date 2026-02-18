# RuleDSL Compiler Contract (`ruledslc`)

## Purpose

`ruledslc` compiles RuleDSL source (`.rule`) into deterministic RuleDSL bytecode (`.axbc`).
The compiler is distributed as a licensed binary for local customer use.

## Stable CLI Surface (MVP)

```text
ruledslc compile <input.rule> -o <output.axbc> [--lang 0.9] [--target axbc3] [--emit-manifest <path.json>]
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

## Determinism Contract

For the same compiler version, same input bytes, and same compile flags, `ruledslc` MUST produce byte-identical `.axbc` output.

`ruledslc` output and manifest generation MUST NOT include:
- timestamps,
- random salts,
- host-specific absolute paths.

## Version Handshake

`ruledslc --version` returns a machine-parseable line:

```text
RuleDSL/1.0.0 (lang=0.9; axbc=3; abi=1; ex2=1)
```

If a field is not supported in a release, it is omitted from the printed tuple.
Current baseline fields are `lang`, `axbc`, and `abi`.

## Compatibility Policy

| Compiler | Language | Bytecode target | SDK ABI | Notes |
| --- | --- | --- | --- | --- |
| `1.0.x` | `0.9` | `axbc3` | `1` | Baseline public contract |

Compatibility rules:
- Compiler major version change MAY introduce breaking compile behavior.
- Compiler minor/patch updates SHOULD keep language compatibility within the same major line.
- Engine MUST reject incompatible bytecode schema versions at load/evaluation time.

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
