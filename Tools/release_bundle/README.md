# Release Bundle Builder

`build_bundle.ps1` assembles a distributable SDK bundle.

## Usage

```powershell
pwsh Tools/release_bundle/build_bundle.ps1   -EngineBin <path-to-ruledsl_capi.dll-or-libruledsl_capi.so>   -CompilerBin <path-to-ruledslc.exe>   -EngineImportLib <path-to-ruledsl_capi.lib>   -Out <output-folder>
```
