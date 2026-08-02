"""RuleDSL MCP rule library loader (Phase 1).

Design contract: docs/design/mcp_server_v0.md (sections 5-6).

Only rules declared in rules/manifest.json are loadable; the directory is
never scanned. Every referenced file is verified against its declared
sha256 at load time; any mismatch is fatal (no partial load). The library
is loaded once at startup and is immutable afterwards - changing rules
means restarting with a new manifest.

Pure standard library. The engine enters only through the optional
`compiler` argument of load_library() (duck-typed: any object with a
compile(source) method, e.g. the public SDK's RuleDSL wrapper), so this
module stays importable and testable without the engine present.
"""

import hashlib
import json
import math
from pathlib import Path

from .errors import SRV_UNKNOWN_RULE_ID, summarize  # noqa: F401 - re-exported by __init__
from .validate import SchemaDeclarationError, check_schema

# v1 is deliberately NOT supported. A v1 manifest declares no input_schema, so
# serving one would keep the unvalidated-input path alive under a "supported"
# banner - and unvalidated input is the defect manifest v2 exists to close.
SUPPORTED_MANIFEST_VERSIONS = (2,)


class LibraryError(Exception):
    """Fatal library-load error. Raised at load time; no partial load."""


class ManifestVersionError(LibraryError):
    """manifest_version is missing or not a supported value."""


class RuleHashMismatchError(LibraryError):
    """A rule file's content does not match its manifest-declared sha256."""


class UnknownRuleIdError(Exception):
    """Call-time error: rule_id not present in the manifest.

    Phase 2 maps this to the server-domain error object
    {error_domain: "server", error_code: 1, error_name: "SRV_UNKNOWN_RULE_ID"}.
    """

    server_error_code = SRV_UNKNOWN_RULE_ID
    server_error_name = "SRV_UNKNOWN_RULE_ID"

    def __init__(self, rule_id):
        self.rule_id = rule_id
        # summarize(), not {rule_id!r}: this message becomes an error message on
        # the wire, and a caller-supplied rule_id is unbounded input.
        super().__init__("unknown rule_id: %s (SRV_UNKNOWN_RULE_ID=%d)"
                         % (summarize(rule_id), self.server_error_code))


class RuleEntry:
    """One manifest-declared rule, verified and (optionally) compiled."""

    __slots__ = ("rule_id", "file", "version", "rule_sha256", "source",
                 "input_schema", "bytecode", "bytecode_sha256")

    def __init__(self, rule_id, file, version, rule_sha256, source,
                 input_schema=None, bytecode=None, bytecode_sha256=None):
        self.rule_id = rule_id
        self.file = file
        self.version = version
        self.rule_sha256 = rule_sha256
        self.source = source
        self.input_schema = input_schema
        self.bytecode = bytecode
        self.bytecode_sha256 = bytecode_sha256

    def __repr__(self):
        return (f"RuleEntry(rule_id={self.rule_id!r}, version={self.version!r}, "
                f"rule_sha256={self.rule_sha256!r}, bytecode_sha256={self.bytecode_sha256!r})")


class Library:
    """Immutable set of manifest-declared rules. Built by load_library() only."""

    def __init__(self, entries, manifest_sha256=None):
        self._entries = dict(entries)
        self.manifest_sha256 = manifest_sha256

    def get(self, rule_id):
        try:
            return self._entries[rule_id]
        except KeyError:
            raise UnknownRuleIdError(rule_id) from None

    def rule_ids(self):
        """Manifest-declared rule ids, sorted for deterministic listing."""
        return sorted(self._entries)

    def __len__(self):
        return len(self._entries)

    def __contains__(self, rule_id):
        return rule_id in self._entries


def _sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def _reject_constant(token):
    """Refuse JSON's non-standard NaN / Infinity tokens.

    Python's json module accepts them by default. A manifest carrying one
    would put a value into an input_schema bound or an enum that no
    conforming JSON reader could produce, and that no comparison can ever
    satisfy - a constraint that looks enforced and never fires.
    """
    raise LibraryError(
        f"manifest contains the non-standard JSON token {token}; "
        f"only finite numbers are accepted")


def _finite_float(text):
    """Refuse a literal that overflows to infinity, e.g. 1e400.

    parse_constant does not see this one: it is a well-formed decimal literal
    that float() silently turns into inf.
    """
    value = float(text)
    if not math.isfinite(value):
        raise LibraryError(
            f"manifest number {text} is not finite (it overflows to {value})")
    return value


def _check_transmittable(node, path):
    """Every string in the manifest must have a UTF-8 form.

    A "\\ud800" escape is legal JSON input and produces a lone surrogate,
    which cannot be encoded as UTF-8. Left alone, a rule id like that is
    servable: the decision log write succeeds (canonical JSON escapes it back)
    while the response to the client fails to encode - so a decision is
    recorded that the caller is told never happened. Fatal at load instead.
    """
    if isinstance(node, str):
        try:
            node.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise LibraryError(
                f"{path} is not encodable as UTF-8 ({exc.reason}); a value that "
                f"cannot cross the wire must not be servable")
    elif isinstance(node, dict):
        for key, value in node.items():
            _check_transmittable(key, f"{path} key {key[:32]!r}"
                                 if isinstance(key, str) else path)
            _check_transmittable(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _check_transmittable(value, f"{path}[{index}]")
    elif isinstance(node, float) and not math.isfinite(node):
        raise LibraryError(f"{path} is not a finite number")


def _bytecode_bytes(compiled):
    data = getattr(compiled, "data", compiled)
    if not isinstance(data, (bytes, bytearray)):
        raise LibraryError(
            f"compiler returned unsupported bytecode type: {type(compiled).__name__}")
    return bytes(data)


def load_library(path, compiler=None):
    """Load and verify a rule library from `path` (directory holding manifest.json).

    Fatal (raises LibraryError subclass, nothing is served) on: missing or
    unreadable manifest, missing/unknown manifest_version, malformed rule
    entries, missing rule files, sha256 mismatch, files escaping the
    library directory, or compile failure.

    If `compiler` is given, every rule is compiled now (startup), and each
    entry carries bytecode + bytecode_sha256. There is no bytecode cache:
    recompiled on every load, by design (see design doc section 6 note).
    """
    root = Path(path)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise LibraryError(f"manifest not found: {manifest_path}")

    try:
        manifest_raw = manifest_path.read_bytes()
        manifest = json.loads(manifest_raw.decode("utf-8"),
                              parse_constant=_reject_constant,
                              parse_float=_finite_float)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LibraryError(f"manifest unreadable: {exc}") from exc
    _check_transmittable(manifest, "manifest")
    manifest_sha256 = _sha256_hex(manifest_raw)

    if not isinstance(manifest, dict) or "manifest_version" not in manifest:
        raise ManifestVersionError(
            "manifest_version missing; refusing to guess the manifest format")
    version = manifest["manifest_version"]
    if version not in SUPPORTED_MANIFEST_VERSIONS:
        raise ManifestVersionError(
            f"unknown manifest_version {version!r}; supported: "
            f"{list(SUPPORTED_MANIFEST_VERSIONS)}. manifest_version 2 adds the "
            f"required per-rule input_schema (docs/design/mcp_server_v0.md "
            f"section 6); a v1 manifest cannot be served because its fields "
            f"would reach the engine unvalidated.")

    rules = manifest.get("rules")
    if not isinstance(rules, dict):
        raise LibraryError("manifest field 'rules' missing or not an object")

    resolved_root = root.resolve()
    entries = {}
    for rule_id, spec in rules.items():
        required = {"file", "sha256", "version", "input_schema"}
        if not isinstance(spec, dict) or not required <= spec.keys():
            raise LibraryError(
                f"rule {rule_id!r}: entry must declare file, sha256, version, "
                f"input_schema")

        # The schema is validated at LOAD time, so a rule whose input contract
        # cannot be understood is never served. Because the manifest is hashed
        # and manifest_sha256 is reported by engine_info, the schemas are
        # tamper-evident at no extra cost.
        try:
            input_schema = check_schema(spec["input_schema"], rule_id)
        except SchemaDeclarationError as exc:
            raise LibraryError(f"rule {rule_id!r}: {exc}") from exc

        rule_path = (root / spec["file"]).resolve()
        if resolved_root not in rule_path.parents and rule_path != resolved_root:
            raise LibraryError(
                f"rule {rule_id!r}: file {spec['file']!r} escapes the library directory")
        if not rule_path.is_file():
            raise LibraryError(f"rule {rule_id!r}: file not found: {spec['file']}")

        raw = rule_path.read_bytes()
        expected = str(spec["sha256"]).lower()
        found = _sha256_hex(raw)
        if found != expected:
            raise RuleHashMismatchError(
                f"rule {rule_id!r}: sha256 mismatch for {spec['file']} "
                f"(expected {expected}, found {found})")

        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LibraryError(f"rule {rule_id!r}: source is not valid UTF-8: {exc}") from exc

        # A NUL ends the C string the compiler receives, so it would compile
        # only the prefix while the sha256 just verified attests to ALL the
        # bytes. The hash would then vouch for more than what actually ran.
        if "\x00" in source:
            raise LibraryError(
                f"rule {rule_id!r}: source contains a NUL byte at offset "
                f"{source.index(chr(0))}; the compiler would compile only the "
                f"prefix while sha256 attests to all {len(raw)} bytes")

        bytecode = bytecode_sha256 = None
        if compiler is not None:
            try:
                bytecode = _bytecode_bytes(compiler.compile(source))
            except LibraryError:
                raise
            except Exception as exc:
                raise LibraryError(f"rule {rule_id!r}: compile failed: {exc}") from exc
            bytecode_sha256 = _sha256_hex(bytecode)

        entries[rule_id] = RuleEntry(
            rule_id=rule_id, file=spec["file"], version=str(spec["version"]),
            rule_sha256=expected, source=source, input_schema=input_schema,
            bytecode=bytecode, bytecode_sha256=bytecode_sha256)

    return Library(entries, manifest_sha256=manifest_sha256)
