"""RuleDSL MCP server (Phase 2) - thin transport wiring, no logic.

Design contract: docs/design/mcp_server_v0.md section 2. All behavior
lives in handlers.py; this module only binds the three handlers to MCP
tools over stdio. The `mcp` package (official Python SDK) is imported
ONLY here, so the core stays testable without an MCP client.

CLI: every path is explicit and required - the server never chooses a
rules directory, log file, or engine library on its own (explicit-input
policy, design doc section 3).
"""

import argparse

from . import handlers
from .library import load_library


def build_server(library, engine, log):
    """Wire the three handlers to MCP tools. Logic-free by design."""
    try:  # official SDK v2
        from mcp.server.mcpserver import MCPServer as _ServerClass
    except ImportError:  # official SDK v1
        from mcp.server.fastmcp import FastMCP as _ServerClass

    server = _ServerClass("ruledsl-mcp")

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
    parser.add_argument("--rules", required=True,
                        help="rule-library directory holding manifest.json")
    parser.add_argument("--decision-log", required=True,
                        help="JSONL decision-record file (appended)")
    parser.add_argument("--engine-lib", required=True,
                        help="path to the RuleDSL engine library "
                             "(ruledsl_capi.dll / .so)")
    args = parser.parse_args(argv)

    from ruledsl import RuleDSL  # public SDK binding

    engine = RuleDSL(args.engine_lib)
    library = load_library(args.rules, compiler=engine)
    with open(args.decision_log, "a", encoding="utf-8", newline="\n") as log:
        server = build_server(library, engine, log)
        server.run()


if __name__ == "__main__":
    main()
