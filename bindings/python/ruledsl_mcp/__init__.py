"""RuleDSL MCP server package (EXPERIMENTAL, incubating in the engine repo).

Design contract: docs/design/mcp_server_v0.md.
Phase 1: rule-library loader (library.py).
Phase 2: tool handlers (handlers.py, pure core) + MCP wiring (server.py).
"""

__version__ = "0.1.0"

from .library import (
    Library,
    LibraryError,
    ManifestVersionError,
    RuleEntry,
    RuleHashMismatchError,
    SRV_UNKNOWN_RULE_ID,
    SUPPORTED_MANIFEST_VERSIONS,
    UnknownRuleIdError,
    load_library,
)

__all__ = [
    "Library",
    "LibraryError",
    "ManifestVersionError",
    "RuleEntry",
    "RuleHashMismatchError",
    "SRV_UNKNOWN_RULE_ID",
    "SUPPORTED_MANIFEST_VERSIONS",
    "UnknownRuleIdError",
    "load_library",
]
