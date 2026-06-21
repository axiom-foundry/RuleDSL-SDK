# 02 Threshold Gate

This example demonstrates a threshold gate pattern: transactions above a hard limit are declined, those in a "gate zone" are reviewed, and low-value transactions are allowed.

The test evaluates `amount=700`, which falls in the review zone (500-1000).

## Commands

Compile and verify the rule (any platform):

```text
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3 --emit-manifest compile_manifest.json
ruledslc verify rules.axbc
```

Build and run — Linux/macOS (gcc or clang):

```bash
cc -std=c11 -I ../../include main.c -L ../../bin -lruledsl_capi -o threshold_eval
LD_LIBRARY_PATH=../../bin ./threshold_eval rules.axbc
```

Build and run — Windows (MSVC):

```powershell
cl /nologo /W4 /I ..\..\include main.c /link /LIBPATH:..\..\bin ruledsl_capi.lib /OUT:threshold_eval.exe
.\threshold_eval.exe rules.axbc
```

Expected output:

```text
ACTION=REVIEW
RESULT=OK
```
