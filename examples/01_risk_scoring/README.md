# 01 Risk Scoring

This example compiles a risk-scoring rule file and evaluates the resulting bytecode.

## Commands

Compile and verify the rule (any platform):

```text
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3 --emit-manifest compile_manifest.json
ruledslc verify rules.axbc
```

Build and run — Linux/macOS (gcc or clang):

```bash
cc -std=c11 -I ../../include main.c -L ../../bin -lruledsl_capi -o risk_eval
LD_LIBRARY_PATH=../../bin ./risk_eval rules.axbc
```

Build and run — Windows (MSVC):

```powershell
cl /nologo /W4 /I ..\..\include main.c /link /LIBPATH:..\..\bin ruledsl_capi.lib /OUT:risk_eval.exe
.\risk_eval.exe rules.axbc
```

Expected output:

```text
ACTION=DECLINE
RESULT=OK
```
