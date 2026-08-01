"""RuleDSL MCP server (Phase 2) - thin transport wiring, no logic.

Design contract: docs/design/mcp_server_v0.md section 2. All behavior
lives in handlers.py; this module only binds the three handlers to MCP
tools over stdio. The `mcp` package (official Python SDK) is imported
ONLY here, so the core stays testable without an MCP client.

CLI: every path is explicit and required - the server never chooses a
rules directory, log file, or engine library on its own (explicit-input
policy, design doc section 3). `--print-example-rules` is an
information-only discovery helper: it prints where the packaged example
library lives and exits; it never becomes an implicit default.
"""

import argparse
import sys
from pathlib import Path

from . import __version__, handlers
from .library import load_library


def example_rules_dir():
    """Directory of the shipped example rule library, or None.

    Pip install: the wheel carries a copy at ruledsl_mcp/examples/rules/
    (assembled at build time from the repository's canonical rules/; CI
    byte-compares the two so they cannot drift). Checkout: that copy does
    not exist, so fall back to the canonical rules/ at the repo root.
    """
    pkg_dir = Path(__file__).resolve().parent
    packaged = pkg_dir / "examples" / "rules"
    if (packaged / "manifest.json").is_file():
        return packaged
    checkout = pkg_dir.parent.parent.parent / "rules"  # <repo>/rules
    if (checkout / "manifest.json").is_file():
        return checkout
    return None


def _python_version_error(version_info):
    """Runtime gate: the `[mcp]` extra's 3.10+ floor cannot be expressed in
    package metadata (the base package supports 3.7+), so it is enforced
    here with a clear message instead of an import-time stack trace."""
    if tuple(version_info[:2]) < (3, 10):
        return ("ruledsl-mcp requires Python 3.10+ (the `mcp` SDK's floor); "
                "this interpreter is %d.%d. The base `ruledsl` package (binding "
                "+ workbench) still works on 3.7+." % tuple(version_info[:2]))
    return None


def build_server(library, engine, log):
    """Wire the three handlers to MCP tools. Logic-free by design.

    serverInfo.version states OUR package version, not the transport SDK's
    default: SDK v2 takes it as a constructor parameter; on SDK v1 the
    low-level Server object owns the field.
    """
    try:  # official SDK v2
        from mcp.server.mcpserver import MCPServer
        server = MCPServer("ruledsl-mcp", version=__version__)
    except ImportError:  # official SDK v1
        from mcp.server.fastmcp import FastMCP
        server = FastMCP("ruledsl-mcp")
        low_level = getattr(server, "_mcp_server", None)
        if low_level is not None and hasattr(low_level, "version"):
            low_level.version = __version__

    @server.tool()
    def list_rules() -> dict:
        """List the callable rules declared in the manifest."""
        return handlers.list_rules(library)

    @server.tool()
    def evaluate_case(rule_id: str, fields: dict, now_utc_ms: float) -> dict:
        """Evaluate one case against a manifest-declared rule.

        now_utc_ms is mandatory: the server never reads a clock.
        """
        return handlers.evaluate_case(library, engine, log,
                                      rule_id, fields, now_utc_ms)

    @server.tool()
    def engine_info() -> dict:
        """Engine, schema, and library identity for this server instance."""
        return handlers.engine_info(library, engine)

    return server


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ruledsl-mcp",
        description="RuleDSL MCP server v0 (EXPERIMENTAL). "
                    "The agent invokes; the engine decides.")
    parser.add_argument("--rules",
                        help="rule-library directory holding manifest.json "
                             "(required)")
    parser.add_argument("--decision-log",
                        help="JSONL decision-record file (appended) (required)")
    parser.add_argument("--engine-lib",
                        help="path to the RuleDSL engine library "
                             "(ruledsl_capi.dll / .so) (required)")
    parser.add_argument("--print-example-rules", action="store_true",
                        help="print the shipped example rule-library path and "
                             "exit (discovery helper; --rules stays explicit)")
    args = parser.parse_args(argv)

    if args.print_example_rules:
        example = example_rules_dir()
        if example is None:
            print("no example rule library found in this installation",
                  file=sys.stderr)
            return 2
        print(example)
        return 0

    gate = _python_version_error(sys.version_info)
    if gate:
        parser.exit(2, gate + "\n")

    missing = [flag for flag, value in (("--rules", args.rules),
                                        ("--decision-log", args.decision_log),
                                        ("--engine-lib", args.engine_lib))
               if not value]
    if missing:
        parser.error("the following arguments are required: " + ", ".join(missing))

    from ruledsl import RuleDSL  # public SDK binding

    engine = RuleDSL(args.engine_lib)
    library = load_library(args.rules, compiler=engine)
    with open(args.decision_log, "a", encoding="utf-8", newline="\n") as log:
        server = build_server(library, engine, log)
        server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
