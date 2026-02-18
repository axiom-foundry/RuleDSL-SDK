# 01 Risk Scoring

This example compiles a risk-scoring rule file and evaluates the resulting bytecode.

## Commands

```powershell
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3 --emit-manifest compile_manifest.json
ruledslc verify rules.axbc
cl /nologo /W4 /I ..\..\include main.c /link /LIBPATH:<ENGINE_LIB_DIR> ruledsl_capi.lib /OUT:risk_eval.exe
.\risk_eval.exe rules.axbc
```

Expected output:

```text
ACTION=DECLINE
RESULT=OK
```
