# 04 KYC Compliance

This example demonstrates boolean logic (`and`, `or`, `not`), list membership (`in`), pattern matching (`match`), and priority ordering.

## Grammar Features Used

- `priority` for evaluation order
- `in` for country blocklist
- `match` for email domain pattern
- `and`, `or`, `not` for compound conditions
- Parentheses for grouping
- Output field assignment (`reason = ...`)

## Commands

Compile and verify the rule (any platform):

```text
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3 --emit-manifest compile_manifest.json
ruledslc verify rules.axbc
```

Build and run — Linux/macOS (gcc or clang):

```bash
cc -std=c11 -I ../../include main.c -L ../../bin -lruledsl_capi -o kyc_eval
LD_LIBRARY_PATH=../../bin ./kyc_eval rules.axbc
```

Build and run — Windows (MSVC):

```powershell
cl /nologo /W4 /I ..\..\include main.c /link /LIBPATH:..\..\bin ruledsl_capi.lib /OUT:kyc_eval.exe
.\kyc_eval.exe rules.axbc
```

Expected output:

```text
ACTION=REVIEW
RESULT=OK
```

The test scenario sends a $2500 transaction from a new, unverified device. The `new_device_review` rule (priority 40) matches because `is_new_device and (amount > 1000 or not is_verified)` is true.
