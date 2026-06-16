# 03 Temporal Rule

This example shows deterministic evaluation with explicit `now_utc_ms` input.

## Commands

```powershell
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3 --emit-manifest compile_manifest.json
ruledslc verify rules.axbc
cl /nologo /W4 /I ..\..\include main.c /link /LIBPATH:<ENGINE_LIB_DIR> ruledsl_capi.lib /OUT:temporal_eval.exe
.\temporal_eval.exe rules.axbc
```

Expected output:

```text
ACTION=REVIEW
RESULT=OK
```
