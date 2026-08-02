"""RuleDSL MCP server - thin transport wiring, no decision logic.

Design contract: docs/design/mcp_server_v0.md sections 2, 2.5 and 2.6. All
behavior lives in handlers.py / validate.py; this module binds the three
handlers to MCP tools over stdio and owns everything transport-shaped:
advertised schemas, argument admission, and failure results.

The `mcp` package is imported ONLY here, so the core stays testable without an
MCP client. The SDK is pinned to 2.x: the 1.x/FastMCP fork was removed so that
failures have exactly ONE shape. Returning a CallToolResult is a passthrough on
2.x, while on 1.x it was JSON-dumped into a text block with isError:false -
strictly worse than raising - and maintaining both would have meant shipping
two different error contracts.

CLI: every path is explicit and required - the server never chooses a rules
directory, log file, or engine library on its own (explicit-input policy,
design doc section 3). `--print-example-rules` is an information-only
discovery helper: it prints where the packaged example library lives and exits;
it never becomes an implicit default.
"""

import argparse
import sys
import traceback
from pathlib import Path
from typing import Any

from . import __version__, errors, handlers, schemas
from .library import load_library

MIN_PYTHON = (3, 10)


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
    if tuple(version_info[:2]) < MIN_PYTHON:
        return ("ruledsl-mcp requires Python %d.%d+ (the `mcp` SDK's floor); "
                "this interpreter is %d.%d. The base `ruledsl` package (binding "
                "+ workbench) still works on 3.7+."
                % (MIN_PYTHON + tuple(version_info[:2])))
    return None


class SchemaWiringError(RuntimeError):
    """The transport SDK did not accept the explicit tool schemas.

    Fatal at startup on purpose: advertising a schema the server does not
    actually honour - or honouring one it does not advertise - is worse than
    refusing to start.
    """


def _failure_result(err):
    """Build the single failure shape: isError with the error object both as
    text and as structured content, so a client can branch on it without
    parsing prose (design doc section 2.6)."""
    from mcp.types import CallToolResult, TextContent
    return CallToolResult(
        content=[TextContent(type="text", text=errors.canonical_json(err))],
        structured_content=err,
        is_error=True,
    )


def _check_arguments(tool_name, arguments):
    """Admit a call: names first, then RAW top-level types.

    Both checks have to happen here, before the SDK touches the arguments.

    Names: the SDK's generated argument model ignores extras by default, so a
    misspelled `now_utc_ms` would arrive as "absent" with the stray key
    silently dropped. Silently dropping part of a caller's request is the same
    class of defect as silently coercing it.

    Types: the SDK pre-parses any string argument whose annotation is not
    `str` with json.loads (pre_parse_json in
    mcp/server/mcpserver/utilities/func_metadata.py). Our parameters are
    annotated `Any` - deliberately, so Pydantic does not coerce - which means
    `Any is not str` and a caller sending fields='{"amount":1}' had it turned
    into a real object before any validation ran, and evaluated normally.
    handlers.check_call_shape is called on the raw dict so the wire and a
    direct in-process call reject it identically, by construction.
    """
    declared = schemas.TOOL_SCHEMAS.get(tool_name)
    if declared is None:
        return
    allowed = set(declared[0].get("properties", {}))
    for name in sorted(arguments or {}):
        if name not in allowed:
            raise errors.ToolFailure(errors.server_error(
                errors.SRV_UNKNOWN_ARGUMENT,
                "argument is not declared by this tool; declared: %s" % sorted(allowed),
                name))

    shape = handlers.check_call_shape(tool_name, arguments or {})
    if shape is not None:
        raise errors.ToolFailure(shape)


def build_server(library, engine, log):
    """Wire the three handlers to MCP tools. Decision-logic-free by design.

    serverInfo.version states OUR package version, not the transport SDK's.
    """
    from mcp.server.mcpserver import MCPServer

    class RuleDSLMCPServer(MCPServer):
        """Adds argument admission and the single failure shape.

        _handle_call_tool (the wire path) delegates to call_tool, so overriding
        it here covers both the wire and any direct in-process call.
        """

        async def call_tool(self, name, arguments, context=None):
            try:
                _check_arguments(name, arguments)
                result = await super().call_tool(name, arguments, context)
            except errors.ToolFailure as exc:
                return _failure_result(exc.error)
            except Exception as exc:  # noqa: BLE001 - nothing escapes the contract
                # stderr is free on MCP stdio and is the only place a stack
                # trace can go without corrupting the protocol stream.
                traceback.print_exc(file=sys.stderr)
                return _failure_result(errors.server_error(
                    errors.SRV_INTERNAL,
                    "unhandled server failure: %s" % type(exc).__name__))

            # A handler reports failure by RETURNING the section-5 error object
            # (it is transport-free by contract). This is the one place that
            # turns it into isError, so a failure can never be delivered as a
            # successful call - which is exactly what an agent orchestrator
            # checking only transport success would have believed.
            if errors.is_error(getattr(result, "structured_content", None)):
                return _failure_result(result.structured_content)
            return result

    server = RuleDSLMCPServer("ruledsl-mcp", version=__version__)

    def _emit(fn, *args):
        """Run a handler and always RETURN a dict.

        A ToolFailure raised deep in a handler must not escape into the SDK,
        which would wrap it as a generic tool error and lose its code; it is
        flattened back into the error object here and classified in call_tool.
        """
        try:
            return fn(*args)
        except errors.ToolFailure as exc:
            return exc.error

    @server.tool()
    def list_rules() -> dict[str, Any]:
        """List the callable rules declared in the manifest.

        Each entry carries the rule's input_schema; satisfy it exactly, because
        evaluate_case rejects fields the schema does not declare.
        """
        return _emit(handlers.list_rules, library)

    @server.tool()
    def evaluate_case(rule_id: str = "", fields: Any = None,
                      now_utc_ms: Any = None) -> dict[str, Any]:
        """Evaluate one case against a manifest-declared rule.

        now_utc_ms is mandatory: the server never reads a clock.

        `fields` and `now_utc_ms` are deliberately annotated `Any`. The SDK
        derives its argument model from these annotations, and a typed
        annotation makes Pydantic's lax mode COERCE - `now_utc_ms: float` would
        turn the string "1700000000000" into a number, silently accepting the
        exact input this server must refuse, and would turn an int into a float
        so the logged record differed between the wire and a direct call. All
        type discipline lives in handlers/validate, where a rejection carries a
        stable code. The schema clients actually see is attached explicitly
        below.

        `rule_id` is the exception, and annotated `str` for a reason that runs
        the other way: the SDK's pre_parse_json step runs json.loads on a
        string argument whose annotation is NOT `str`, so a rule id of "null"
        or "{}" - both perfectly ordinary strings, and both things a caller can
        send - arrived at the handler as None or as a dict. The wire then
        reported "rule_id must be a string" where a direct call correctly
        reported an unknown rule id. Annotating `str` opts this one parameter
        out of pre-parsing. Nothing is coerced by it: _check_arguments has
        already rejected any non-string rule_id before the SDK sees the call.
        """
        return _emit(handlers.evaluate_case, library, engine, log,
                     rule_id, fields, now_utc_ms)

    @server.tool()
    def engine_info() -> dict[str, Any]:
        """Engine, schema, and library identity for this server instance."""
        return _emit(handlers.engine_info, library, engine)

    _attach_schemas(server)
    return server


def _attach_schemas(server):
    """Advertise the hand-written schemas instead of the derived ones.

    The SDK takes no schema arguments on the decorator, so they are set on the
    registered tool and read back to confirm the write took effect. A silent
    failure here would advertise a contract the server does not honour, so it
    is fatal at startup rather than a warning.

    The generated argument model is also switched to `extra="forbid"`, which
    makes the advertised `additionalProperties: false` true at the SDK layer as
    well - defence in depth behind _check_arguments, which is what produces the
    typed SRV_UNKNOWN_ARGUMENT.
    """
    manager = getattr(server, "_tool_manager", None)
    if manager is None or not hasattr(manager, "get_tool"):
        raise SchemaWiringError(
            "this mcp SDK exposes no tool registry, so explicit schemas cannot "
            "be advertised (see docs/design/mcp_server_v0.md section 2.5)")

    for name, (input_schema, output_schema) in schemas.TOOL_SCHEMAS.items():
        tool = manager.get_tool(name)
        if tool is None:
            raise SchemaWiringError("tool %r did not register" % name)
        if not hasattr(tool, "parameters") or not hasattr(tool, "output_schema"):
            raise SchemaWiringError(
                "this mcp SDK cannot advertise explicit input/output schemas "
                "for %r; require mcp>=2.0,<3" % name)

        tool.parameters = input_schema
        tool.output_schema = output_schema
        if tool.parameters != input_schema or tool.output_schema != output_schema:
            raise SchemaWiringError("schema write for %r did not take effect" % name)

        arg_model = getattr(getattr(tool, "fn_metadata", None), "arg_model", None)
        if arg_model is not None and hasattr(arg_model, "model_config"):
            arg_model.model_config["extra"] = "forbid"
            arg_model.model_rebuild(force=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ruledsl-mcp",
        description="RuleDSL MCP server (EXPERIMENTAL). "
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

    # The decision log is opened FIRST: an unwritable path must fail before the
    # engine is loaded and the whole library is compiled, not after.
    with open(args.decision_log, "a", encoding="utf-8", newline="\n") as log:
        engine = RuleDSL(args.engine_lib)
        try:
            library = load_library(args.rules, compiler=engine)
            server = build_server(library, engine, log)
            server.run()
        finally:
            # Deterministic: never rely on __del__ at interpreter shutdown.
            engine.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
