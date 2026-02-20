# Contributor Notes

## Encoding: UTF-8 (no BOM)

All text files MUST be UTF-8 without BOM.
Windows PowerShell `Set-Content -Encoding utf8` may emit BOM.
Prefer repository line-ending discipline and editor settings that save as UTF-8 (not UTF-8 with BOM).
Tip: in PowerShell 7, `-Encoding utf8NoBOM` is available.
