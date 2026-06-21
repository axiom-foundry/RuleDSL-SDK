# 03 Temporal Rule

This example shows deterministic evaluation with explicit `now_utc_ms` input.

## Commands

Compile and verify the rule (any platform):

```text
ruledslc compile rules.rule -o rules.axbc --lang 0.9 --target axbc3 --emit-manifest compile_manifest.json
ruledslc verify rules.axbc
```

Build and run — Linux/macOS (gcc or clang):

```bash
cc -std=c11 -I ../../include main.c -L ../../bin -lruledsl_capi -o temporal_eval
LD_LIBRARY_PATH=../../bin ./temporal_eval rules.axbc
```

Build and run — Windows (MSVC):

```powershell
cl /nologo /W4 /I ..\..\include main.c /link /LIBPATH:..\..\bin ruledsl_capi.lib /OUT:temporal_eval.exe
.\temporal_eval.exe rules.axbc
```

Expected output:

```text
ACTION=REVIEW
RESULT=OK
```
