# 05 Velocity Limit

This example demonstrates arithmetic expressions, velocity limit clauses with currency tags, computed risk scores, and range-based conditions.

## Grammar Features Used

- `priority` for evaluation order
- Arithmetic in `then` clause: `(amount / 500) + 20`
- `limit ... per` with currency: `LIMIT 3000 USD PER 1 D`
- Range conditions: `amount > 5000 AND amount <= 25000`
- Output field assignment: `risk_score = ...`, `reason = ...`

## Commands

Compile and verify the rule (any platform):

```text
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3 --emit-manifest compile_manifest.json
ruledslc verify rules.axbc
```

Build and run — Linux/macOS (gcc or clang):

```bash
cc -std=c11 -I ../../include main.c -L ../../bin -lruledsl_capi -o velocity_eval
LD_LIBRARY_PATH=../../bin ./velocity_eval rules.axbc
```

Build and run — Windows (MSVC):

```powershell
cl /nologo /W4 /I ..\..\include main.c /link /LIBPATH:..\..\bin ruledsl_capi.lib /OUT:velocity_eval.exe
.\velocity_eval.exe rules.axbc
```

Expected output:

```text
ACTION=LIMIT
RESULT=OK
```

The test scenario sends an $8000 transaction. The `high_value_daily_cap` rule (priority 100) matches because `amount > 5000 and amount <= 25000` is true, applying a daily limit of 3000 USD.
