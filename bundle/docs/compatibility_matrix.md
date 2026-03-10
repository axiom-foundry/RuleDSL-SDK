# RuleDSL Compatibility Matrix

This matrix defines the supported compile-to-evaluate path for the public SDK contract.

| Compiler Version | Language Impl | AXBC Version | Engine ABI | Minimum Engine Version |
| --- | --- | --- | --- | --- |
| 1.0.x | 1.0 (impl 0.9) | 3 | 1 | 1.0.0 |

> **Note**: The compiler reports `lang=0.9` in its version string. This is the internal implementation tag for the v1.0 language specification. All v1.0 grammar productions are fully implemented.

## Interpretation

- `ruledslc compile` MUST target `--lang 0.9 --target axbc3` for this line.
- `ruledslc verify` MUST report `STATUS=OK` before evaluation.
- `ax_check_bytecode_compatibility` MUST return `AX_STATUS_OK` before calling `ax_eval_bytecode`.
- If compiler/engine contract versions differ from this table, treat the artifact as incompatible until an updated matrix is published.