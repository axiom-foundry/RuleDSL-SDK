"""RuleDSL MCP server package (EXPERIMENTAL).

Design contract: docs/design/mcp_server_v0.md.

  errors.py    server-domain error registry (the section-5 contract)
  validate.py  fail-closed input validation, engine-free
  schemas.py   the advertised MCP tool schemas
  library.py   rule-library loader (manifest v2, verified + compiled at load)
  handlers.py  tool logic, transport-free
  server.py    MCP wiring: schemas, argument admission, failure results

This version is what serverInfo.version reports; it is independent of the
`ruledsl` package version and of the rule-library `manifest_version`.
"""

__version__ = "0.2.0"

from .errors import (
    ENGINE_DOMAIN,
    SERVER_DOMAIN,
    SERVER_ERROR_NAMES,
    SRV_FIELD_NAME_INVALID,
    SRV_FIELDS_TOO_LARGE,
    SRV_INTERNAL,
    SRV_NOW_UTC_MS_NOT_INTEGER,
    SRV_RESERVED_FIELD,
    SRV_SCHEMA_VIOLATION,
    SRV_UNKNOWN_ARGUMENT,
    SRV_UNKNOWN_RULE_ID,
    SRV_UNSAFE_FIELD_VALUE,
    ToolFailure,
    canonical_json,
    is_error,
)
from .library import (
    Library,
    LibraryError,
    ManifestVersionError,
    RuleEntry,
    RuleHashMismatchError,
    SUPPORTED_MANIFEST_VERSIONS,
    UnknownRuleIdError,
    load_library,
)

__all__ = [
    "ENGINE_DOMAIN",
    "Library",
    "LibraryError",
    "ManifestVersionError",
    "RuleEntry",
    "RuleHashMismatchError",
    "SERVER_DOMAIN",
    "SERVER_ERROR_NAMES",
    "SRV_FIELDS_TOO_LARGE",
    "SRV_FIELD_NAME_INVALID",
    "SRV_INTERNAL",
    "SRV_NOW_UTC_MS_NOT_INTEGER",
    "SRV_RESERVED_FIELD",
    "SRV_SCHEMA_VIOLATION",
    "SRV_UNKNOWN_ARGUMENT",
    "SRV_UNKNOWN_RULE_ID",
    "SRV_UNSAFE_FIELD_VALUE",
    "SUPPORTED_MANIFEST_VERSIONS",
    "ToolFailure",
    "UnknownRuleIdError",
    "canonical_json",
    "is_error",
    "load_library",
]
