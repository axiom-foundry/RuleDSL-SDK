# Customer Verification Guide

## 1) Verify bundle integrity

1. Read `manifests/HASHES.txt` from the delivery bundle.
2. Compute SHA256 for each listed file.
3. Compare results line-by-line.
4. Stop integration if any hash mismatches.

Canonical line format:

```text
<sha256>  <relative_path>
```

## 2) Verify compiler authenticity

- Run `ruledslc --version` and record output.
- Validate the compiler file hash against vendor-published `HASHES.txt`.
- If hash and declared version do not match expected release records, treat the binary as untrusted.

## 3) Compile -> verify -> evaluate

```text
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3
ruledslc verify rules.axbc
# then evaluate using the RuleDSL C API
```

Expected `verify` success output contains:

- `STATUS=OK`
- `AXBC=<supported-version>`
- `LANG=<supported-language>`
- `ABI=<supported-abi>`

## 4) Compatibility check before evaluation

Use the C API compatibility pre-check before evaluation:

- `ax_check_bytecode_compatibility(...)`

If compatibility status is not OK, do not call evaluation.

## 5) What to do on mismatch

### Hash mismatch

- Do not run binaries.
- Request a fresh bundle from the vendor.
- Provide the mismatched path and computed hash.

### `ruledslc verify` incompatibility

- Confirm compiler version and target flags.
- Confirm engine and ABI compatibility using `docs/compatibility_matrix.md`.
- Rebuild bytecode with the vendor-approved compiler version.

### Compatibility API failure

- Treat as version mismatch or invalid artifact.
- Roll back to last-known-good bundle and bytecode pair.
- Open a support ticket with hashes, versions, and error output.