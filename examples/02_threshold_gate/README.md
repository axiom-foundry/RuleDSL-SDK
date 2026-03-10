# 02 Threshold Gate

This example demonstrates a threshold gate pattern: transactions above a hard limit are declined, those in a "gate zone" are reviewed, and low-value transactions are allowed.

The test evaluates `amount=700`, which falls in the review zone (500-1000).

## Commands

```powershell
ruledslc compile rules.rule -o rules.axbc --lang 1.0 --target axbc3 --emit-manifest compile_manifest.json
ruledslc verify rules.axbc
cl /nologo /W4 /I ..\..\include main.c /link /LIBPATH:<ENGINE_LIB_DIR> ruledsl_capi.lib /OUT:threshold_eval.exe
.\threshold_eval.exe rules.axbc
```

Expected output:

```text
ACTION=REVIEW
RESULT=OK
```
