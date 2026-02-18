# 02 Threshold Gate

This example compiles a threshold gate policy and evaluates the resulting decision.

## Commands

```powershell
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3 --emit-manifest compile_manifest.json
cl /nologo /W4 /I ..\..\include main.c /link /LIBPATH:<ENGINE_LIB_DIR> ruledsl_capi.lib /OUT:threshold_eval.exe
.\threshold_eval.exe rules.axbc
```

Expected output:

```text
ACTION=DECLINE
RESULT=OK
```
