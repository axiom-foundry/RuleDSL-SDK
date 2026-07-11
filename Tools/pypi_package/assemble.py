"""Assemble the `ruledsl` package sources from bindings/python/ (build time).

The repository keeps the binding and the workbench as flat files (that is
what the SDK bundle ships); this script maps them into a proper package:

    bindings/python/ruledsl.py    ->  build_src/ruledsl/__init__.py
    bindings/python/workbench.py  ->  build_src/ruledsl/workbench.py
    LICENSE (repo root)           ->  LICENSE

Run from this directory, then `python -m build`.
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SRC = REPO / "bindings" / "python"
OUT = HERE / "build_src" / "ruledsl"

shutil.rmtree(HERE / "build_src", ignore_errors=True)
OUT.mkdir(parents=True)
shutil.copyfile(SRC / "ruledsl.py", OUT / "__init__.py")
shutil.copyfile(SRC / "workbench.py", OUT / "workbench.py")
shutil.copyfile(REPO / "LICENSE", HERE / "LICENSE")
print("assembled:", OUT)
