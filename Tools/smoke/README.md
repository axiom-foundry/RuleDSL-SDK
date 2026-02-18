# Compiler Smoke Test

`compiler_smoke_test.ps1` validates customer-facing compiler/evaluator workflow.

## Usage

```powershell
pwsh Tools/smoke/compiler_smoke_test.ps1   -CompilerBin <path-to-ruledslc.exe>   -EngineLibDir <path-containing-ruledsl_capi.dll-and-.lib>
```

Reports are written to:
- `reports/compiler_smoke_report.md`
- `reports/compiler_smoke_report.json`
