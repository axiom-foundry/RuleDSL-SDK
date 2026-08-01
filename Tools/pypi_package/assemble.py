"""Assemble the `ruledsl` package sources from bindings/python/ (build time).

The repository keeps the binding and the workbench as flat files (that is
what the SDK bundle ships); this script maps them into a proper package:

    bindings/python/ruledsl.py     ->  build_src/ruledsl/__init__.py
    bindings/python/workbench.py   ->  build_src/ruledsl/workbench.py
    bindings/python/ruledsl_mcp/   ->  build_src/ruledsl_mcp/   (already a package)
    rules/ (canonical)             ->  build_src/ruledsl_mcp/examples/rules/
    LICENSE (repo root)            ->  LICENSE

The example rule library is copied from the repository's canonical rules/
at build time, so the wheel is self-contained (ruledsl-mcp
--print-example-rules) while the repo keeps a single source of truth; CI
byte-compares the installed copy against rules/ to rule out drift.

Run from this directory, then `python -m build`.
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SRC = REPO / "bindings" / "python"
OUT = HERE / "build_src" / "ruledsl"
OUT_MCP = HERE / "build_src" / "ruledsl_mcp"

shutil.rmtree(HERE / "build_src", ignore_errors=True)
OUT.mkdir(parents=True)
shutil.copyfile(SRC / "ruledsl.py", OUT / "__init__.py")
shutil.copyfile(SRC / "workbench.py", OUT / "workbench.py")
OUT_MCP.mkdir()
for module in sorted((SRC / "ruledsl_mcp").glob("*.py")):
    shutil.copyfile(module, OUT_MCP / module.name)
EXAMPLES = OUT_MCP / "examples" / "rules"
EXAMPLES.mkdir(parents=True)
for rule_file in sorted((REPO / "rules").iterdir()):
    if rule_file.is_file():
        shutil.copyfile(rule_file, EXAMPLES / rule_file.name)
shutil.copyfile(REPO / "LICENSE", HERE / "LICENSE")
print("assembled:", OUT, "and", OUT_MCP, "(+ example rules)")
