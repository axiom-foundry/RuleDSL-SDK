"""Thin delegation wrapper - the smoke client lives in the package now.

Canonical invocation: python -m ruledsl_mcp.smoke  (see docs/mcp_quickstart.md).
This wrapper keeps the historical checkout/CI invocation working from the
repository tree: it puts bindings/python on sys.path and delegates. Flags are
unchanged; --wrapper and --rules are optional there too (--rules defaults to
the packaged example library, which resolves to this repo's rules/ on a
checkout).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "bindings" / "python"))

from ruledsl_mcp.smoke import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
