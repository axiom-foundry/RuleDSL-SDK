# RuleDSL Compatibility Matrix

This matrix defines the supported compile-to-evaluate path for the public SDK contract.

| Compiler Version | Language Version | AXBC Version | Engine ABI | Minimum Engine Version |
| --- | --- | --- | --- | --- |
| 1.0.x | 0.9 | 3 | 1 | 1.0.0 |

## Interpretation

- `ruledslc compile` MUST target `--lang 0.9 --target axbc3` for this line.
- `ruledslc verify` MUST report `STATUS=OK` before evaluation.
- `ax_check_bytecode_compatibility` MUST return `AX_STATUS_OK` before calling `ax_eval_bytecode`.
- If compiler/engine contract versions differ from this table, treat the artifact as incompatible until an updated matrix is published.