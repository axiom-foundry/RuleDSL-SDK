# Customer Verification Guide

## 1) Verify bundle integrity

1. From the bundle root, verify every file against `manifests/HASHES.txt`:

```bash
# POSIX (Linux/macOS) - run from the bundle root
sha256sum -c manifests/HASHES.txt
```

```powershell
# Windows PowerShell - run from the bundle root
Get-Content manifests/HASHES.txt | ForEach-Object {
  $sha, $rel = ($_ -split '  ', 2)
  $actual = (Get-FileHash -Algorithm SHA256 $rel).Hash.ToLowerInvariant()
  if ($actual -ne $sha) { Write-Error "HASH MISMATCH: $rel" }
}
```

2. Stop integration if any line reports a mismatch.

`manifests/HASHES.txt` uses two spaces between hash and path, is sorted by `<relative_path>`, and excludes itself:

```text
<sha256>  <relative_path>
```

## 2) Verify compiler authenticity

- Run `ruledslc --version` and record output.
- Validate the compiler file hash against the entry for `bin/ruledslc` (or `bin/ruledslc.exe`) in the bundle's `manifests/HASHES.txt`.
- If hash and declared version do not match expected release records, treat the binary as untrusted.

## 3) Compile -> verify -> evaluate

```text
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3
ruledslc verify rules.axbc
# then evaluate using the RuleDSL C API (see examples/01_risk_scoring/main.c)
```

Expected `verify` success output contains:

- `STATUS=OK`
- `AXBC=<supported-version>`
- `LANG=<supported-language>`
- `ABI=<supported-abi>`

> `LANG` reports the language implementation tag (`0.9`) for the v1.0 specification — this is expected. See [`compatibility_matrix.md`](../compatibility_matrix.md) for the canonical 1.0/0.9 reconciliation.

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