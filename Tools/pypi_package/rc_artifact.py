"""Create and verify the immutable RuleDSL 1.2.0 PyPI RC artifact.

The RC build and publish workflows intentionally share this implementation.
Publishing must never infer trust from filenames alone: the GitHub workflow
identity is checked separately, then this module verifies the downloaded bytes
against both RC_METADATA.json and SHA256SUMS.txt.
"""

import argparse
import email
import hashlib
import json
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE_NAME = "ruledsl"
PACKAGE_VERSION = "1.2.0"
REQUIRES_PYTHON = ">=3.7"
WHEEL_TAG = "py3-none-any"
WHEEL_FILENAME = "ruledsl-1.2.0-py3-none-any.whl"
SDIST_FILENAME = "ruledsl-1.2.0.tar.gz"
METADATA_FILENAME = "RC_METADATA.json"
CHECKSUM_FILENAME = "SHA256SUMS.txt"
TESTPYPI_REGISTRY_FILENAME = "TESTPYPI_REGISTRY.json"
TESTPYPI_RECEIPT_FILENAME = "TESTPYPI_VERIFICATION.json"
TESTPYPI_JSON_URL = "https://test.pypi.org/pypi/ruledsl/1.2.0/json"
TESTPYPI_FILE_HOST = "test-files.pythonhosted.org"
REPOSITORY = "axiom-foundry/RuleDSL-SDK"
RC_WORKFLOW = ".github/workflows/pypi-rc-build.yml"
PUBLISH_WORKFLOW = ".github/workflows/pypi-publish.yml"
SCHEMA_VERSION = 1

DISTRIBUTION_FILENAMES = (WHEEL_FILENAME, SDIST_FILENAME)
BUNDLE_FILENAMES = frozenset(
    (WHEEL_FILENAME, SDIST_FILENAME, METADATA_FILENAME, CHECKSUM_FILENAME)
)
TESTPYPI_REGISTRY_FILENAMES = frozenset(
    (WHEEL_FILENAME, SDIST_FILENAME, TESTPYPI_REGISTRY_FILENAME)
)
TESTPYPI_RECEIPT_CHECKS = (
    "registry-json-exact-file-set",
    "registry-sha256-matches-rc",
    "download-sha256-matches-rc",
    "wheel-clean-venv-install",
    "pip-check",
    "package-imports",
    "mcp-version-0.2.0",
    "console-help",
)
MAX_BUNDLE_FILE_BYTES = 100 * 1024 * 1024
MAX_BUNDLE_BYTES = 200 * 1024 * 1024
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_POSITIVE_ID_RE = re.compile(r"^[1-9][0-9]*$")


class ContractError(ValueError):
    """An RC artifact or dispatch input violates the release contract."""


def _fail(message):
    raise ContractError(message)


def _require_exact_keys(value, expected, context):
    if not isinstance(value, dict):
        _fail("%s must be a JSON object" % context)
    actual = set(value)
    expected = set(expected)
    if actual != expected:
        _fail(
            "%s keys differ: missing=%s unexpected=%s"
            % (context, sorted(expected - actual), sorted(actual - expected))
        )


def _require_string(value, context):
    if not isinstance(value, str) or not value:
        _fail("%s must be a non-empty string" % context)
    return value


def _require_sha(value, context):
    value = _require_string(value, context)
    if not _SHA_RE.fullmatch(value):
        _fail("%s must be a lowercase 40-character Git SHA" % context)
    return value


def _require_sha256(value, context):
    value = _require_string(value, context)
    if not _SHA256_RE.fullmatch(value):
        _fail("%s must be a lowercase 64-character SHA-256" % context)
    return value


def _require_positive_id(value, context):
    value = str(value)
    if not _POSITIVE_ID_RE.fullmatch(value):
        _fail("%s must be a positive decimal integer" % context)
    return value


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_file(path, context):
    if path.is_symlink() or not path.is_file():
        _fail("%s must be a regular file: %s" % (context, path))


def _directory_filenames(directory, context):
    if directory.is_symlink() or not directory.is_dir():
        _fail("%s must be a real directory: %s" % (context, directory))
    names = set()
    for entry in directory.iterdir():
        if entry.is_symlink() or not entry.is_file():
            _fail("%s may contain regular files only: %s" % (context, entry.name))
        names.add(entry.name)
    return names


def _require_file_set(directory, expected, context):
    actual = _directory_filenames(directory, context)
    expected = set(expected)
    if actual != expected:
        _fail(
            "%s file set differs: missing=%s unexpected=%s"
            % (context, sorted(expected - actual), sorted(actual - expected))
        )


def _read_message(raw, context):
    message = email.message_from_bytes(raw)
    for field in ("Name", "Version", "Requires-Python"):
        values = message.get_all(field, [])
        if len(values) != 1:
            _fail("%s must contain exactly one %s field" % (context, field))
    return message


def verify_distribution_metadata(directory):
    """Verify filenames and embedded wheel/sdist package metadata."""
    directory = Path(directory)
    _require_file_set(directory, DISTRIBUTION_FILENAMES, "distribution directory")
    wheel = directory / WHEEL_FILENAME
    sdist = directory / SDIST_FILENAME

    with zipfile.ZipFile(str(wheel), "r") as archive:
        bad = archive.testzip()
        if bad is not None:
            _fail("wheel CRC check failed for %s" % bad)
        names = archive.namelist()
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        wheel_names = [name for name in names if name.endswith(".dist-info/WHEEL")]
        expected_prefix = "ruledsl-1.2.0.dist-info/"
        if metadata_names != [expected_prefix + "METADATA"]:
            _fail("wheel must contain exactly the expected METADATA path")
        if wheel_names != [expected_prefix + "WHEEL"]:
            _fail("wheel must contain exactly the expected WHEEL path")
        package_metadata = _read_message(
            archive.read(metadata_names[0]), "wheel METADATA"
        )
        wheel_metadata = email.message_from_bytes(archive.read(wheel_names[0]))

    if package_metadata["Name"] != PACKAGE_NAME:
        _fail("wheel Name must be %s" % PACKAGE_NAME)
    if package_metadata["Version"] != PACKAGE_VERSION:
        _fail("wheel Version must be %s" % PACKAGE_VERSION)
    if package_metadata["Requires-Python"] != REQUIRES_PYTHON:
        _fail("wheel Requires-Python must be %s" % REQUIRES_PYTHON)
    tags = wheel_metadata.get_all("Tag", [])
    if tags != [WHEEL_TAG]:
        _fail("wheel Tag must be exactly %s" % WHEEL_TAG)

    pkg_info_name = "ruledsl-1.2.0/PKG-INFO"
    with tarfile.open(str(sdist), "r:gz") as archive:
        matches = [member for member in archive.getmembers() if member.name == pkg_info_name]
        if len(matches) != 1 or not matches[0].isfile():
            _fail("sdist must contain exactly one regular %s" % pkg_info_name)
        stream = archive.extractfile(matches[0])
        if stream is None:
            _fail("could not read sdist PKG-INFO")
        sdist_metadata = _read_message(stream.read(), "sdist PKG-INFO")

    if sdist_metadata["Name"] != PACKAGE_NAME:
        _fail("sdist Name must be %s" % PACKAGE_NAME)
    if sdist_metadata["Version"] != PACKAGE_VERSION:
        _fail("sdist Version must be %s" % PACKAGE_VERSION)
    if sdist_metadata["Requires-Python"] != REQUIRES_PYTHON:
        _fail("sdist Requires-Python must be %s" % REQUIRES_PYTHON)

    return {
        "name": PACKAGE_NAME,
        "version": PACKAGE_VERSION,
        "requires_python": REQUIRES_PYTHON,
        "wheel_tag": WHEEL_TAG,
    }


def _json_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def _load_json_file(path, context):
    _regular_file(path, context)
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream, object_pairs_hook=_json_no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("invalid %s: %s" % (context, exc))


def _load_metadata(path):
    return _load_json_file(path, "RC metadata")


def _validate_metadata_shape(metadata):
    _require_exact_keys(
        metadata,
        ("schema_version", "package", "source", "github_actions", "artifacts"),
        "RC metadata",
    )
    if type(metadata["schema_version"]) is not int or metadata["schema_version"] != SCHEMA_VERSION:
        _fail("unsupported RC metadata schema_version")

    package = metadata["package"]
    _require_exact_keys(
        package, ("name", "version", "requires_python", "wheel_tag"), "package"
    )
    expected_package = {
        "name": PACKAGE_NAME,
        "version": PACKAGE_VERSION,
        "requires_python": REQUIRES_PYTHON,
        "wheel_tag": WHEEL_TAG,
    }
    if package != expected_package:
        _fail("package metadata does not match the ruledsl 1.2.0 contract")

    source = metadata["source"]
    _require_exact_keys(source, ("commit_sha", "tree_hash"), "source")
    _require_sha(source["commit_sha"], "source.commit_sha")
    _require_sha(source["tree_hash"], "source.tree_hash")

    actions = metadata["github_actions"]
    _require_exact_keys(
        actions, ("repository", "workflow", "run_id", "run_attempt"), "github_actions"
    )
    _require_string(actions["repository"], "github_actions.repository")
    _require_string(actions["workflow"], "github_actions.workflow")
    _require_positive_id(actions["run_id"], "github_actions.run_id")
    _require_positive_id(actions["run_attempt"], "github_actions.run_attempt")

    artifacts = metadata["artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        _fail("artifacts must contain exactly the wheel and sdist")
    expected_kinds = {WHEEL_FILENAME: "wheel", SDIST_FILENAME: "sdist"}
    found = {}
    for index, artifact in enumerate(artifacts):
        context = "artifacts[%d]" % index
        _require_exact_keys(artifact, ("filename", "kind", "sha256", "size"), context)
        filename = _require_string(artifact["filename"], context + ".filename")
        if filename not in expected_kinds or filename in found:
            _fail("artifacts contains an unexpected or duplicate filename")
        if artifact["kind"] != expected_kinds[filename]:
            _fail("%s kind does not match its filename" % context)
        _require_sha256(artifact["sha256"], context + ".sha256")
        if type(artifact["size"]) is not int or artifact["size"] <= 0:
            _fail("%s.size must be a positive integer" % context)
        found[filename] = artifact
    if set(found) != set(expected_kinds):
        _fail("artifacts does not contain the exact wheel and sdist")
    return found


def _parse_checksum_manifest(path):
    _regular_file(path, "checksum manifest")
    entries = {}
    with path.open("r", encoding="ascii", newline="") as stream:
        lines = stream.read().splitlines()
    if len(lines) != 3 or any(not line for line in lines):
        _fail("SHA256SUMS.txt must contain exactly three non-empty lines")
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None:
            _fail("invalid SHA256SUMS.txt line: %r" % line)
        digest, filename = match.groups()
        if filename in entries:
            _fail("duplicate checksum entry: %s" % filename)
        entries[filename] = digest
    expected = {WHEEL_FILENAME, SDIST_FILENAME, METADATA_FILENAME}
    if set(entries) != expected:
        _fail("SHA256SUMS.txt must cover exactly wheel, sdist, and RC metadata")
    return entries


def _identity_expectations(
    metadata,
    expected_source_sha,
    expected_tree_hash,
    expected_version,
    expected_run_id,
    expected_run_attempt,
    expected_repository,
    expected_workflow,
):
    expected_source_sha = _require_sha(expected_source_sha, "expected source SHA")
    expected_tree_hash = _require_sha(expected_tree_hash, "expected tree hash")
    expected_run_id = _require_positive_id(expected_run_id, "expected run ID")
    expected_run_attempt = _require_positive_id(
        expected_run_attempt, "expected run attempt"
    )
    if expected_version != PACKAGE_VERSION:
        _fail("expected version must be %s" % PACKAGE_VERSION)
    if expected_repository != REPOSITORY:
        _fail("expected repository must be %s" % REPOSITORY)
    if expected_workflow != RC_WORKFLOW:
        _fail("expected workflow must be %s" % RC_WORKFLOW)

    expected = {
        "source.commit_sha": (metadata["source"]["commit_sha"], expected_source_sha),
        "source.tree_hash": (metadata["source"]["tree_hash"], expected_tree_hash),
        "package.version": (metadata["package"]["version"], expected_version),
        "github_actions.run_id": (
            str(metadata["github_actions"]["run_id"]),
            expected_run_id,
        ),
        "github_actions.run_attempt": (
            str(metadata["github_actions"]["run_attempt"]),
            expected_run_attempt,
        ),
        "github_actions.repository": (
            metadata["github_actions"]["repository"],
            expected_repository,
        ),
        "github_actions.workflow": (
            metadata["github_actions"]["workflow"],
            expected_workflow,
        ),
    }
    mismatches = [name for name, pair in expected.items() if pair[0] != pair[1]]
    if mismatches:
        _fail("RC identity mismatch: %s" % ", ".join(sorted(mismatches)))


def create_bundle(
    dist_dir,
    output_dir,
    source_sha,
    tree_hash,
    run_id,
    run_attempt,
    repository=REPOSITORY,
    workflow=RC_WORKFLOW,
):
    """Create the four-file RC artifact from an already-built distribution."""
    dist_dir = Path(dist_dir)
    output_dir = Path(output_dir)
    source_sha = _require_sha(source_sha, "source SHA")
    tree_hash = _require_sha(tree_hash, "tree hash")
    run_id = _require_positive_id(run_id, "run ID")
    run_attempt = _require_positive_id(run_attempt, "run attempt")
    if repository != REPOSITORY:
        _fail("repository must be %s" % REPOSITORY)
    if workflow != RC_WORKFLOW:
        _fail("workflow must be %s" % RC_WORKFLOW)
    if output_dir.exists():
        _fail("output directory already exists: %s" % output_dir)

    package = verify_distribution_metadata(dist_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=output_dir.name + ".", dir=str(output_dir.parent)))
    try:
        for filename in DISTRIBUTION_FILENAMES:
            shutil.copyfile(str(dist_dir / filename), str(staging / filename))

        artifacts = []
        for filename, kind in ((WHEEL_FILENAME, "wheel"), (SDIST_FILENAME, "sdist")):
            path = staging / filename
            artifacts.append(
                {
                    "filename": filename,
                    "kind": kind,
                    "sha256": _sha256(path),
                    "size": path.stat().st_size,
                }
            )
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "package": package,
            "source": {"commit_sha": source_sha, "tree_hash": tree_hash},
            "github_actions": {
                "repository": repository,
                "workflow": workflow,
                "run_id": run_id,
                "run_attempt": run_attempt,
            },
            "artifacts": artifacts,
        }
        metadata_path = staging / METADATA_FILENAME
        with metadata_path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(metadata, stream, indent=2, sort_keys=True)
            stream.write("\n")

        checksummed = (METADATA_FILENAME, SDIST_FILENAME, WHEEL_FILENAME)
        with (staging / CHECKSUM_FILENAME).open(
            "w", encoding="ascii", newline="\n"
        ) as stream:
            for filename in checksummed:
                stream.write("%s  %s\n" % (_sha256(staging / filename), filename))

        staging.replace(output_dir)
    except Exception:
        shutil.rmtree(str(staging), ignore_errors=True)
        raise
    return metadata


def verify_bundle(
    artifact_dir,
    expected_source_sha,
    expected_tree_hash,
    expected_version,
    expected_run_id,
    expected_run_attempt,
    expected_repository=REPOSITORY,
    expected_workflow=RC_WORKFLOW,
):
    """Fail closed unless an extracted RC artifact matches every expectation."""
    artifact_dir = Path(artifact_dir)
    _require_file_set(artifact_dir, BUNDLE_FILENAMES, "RC artifact directory")
    metadata = _load_metadata(artifact_dir / METADATA_FILENAME)
    artifacts = _validate_metadata_shape(metadata)
    _identity_expectations(
        metadata,
        expected_source_sha,
        expected_tree_hash,
        expected_version,
        expected_run_id,
        expected_run_attempt,
        expected_repository,
        expected_workflow,
    )

    checksums = _parse_checksum_manifest(artifact_dir / CHECKSUM_FILENAME)
    for filename, expected_digest in checksums.items():
        actual_digest = _sha256(artifact_dir / filename)
        if actual_digest != expected_digest:
            _fail("SHA256SUMS mismatch for %s" % filename)

    for filename, artifact in artifacts.items():
        path = artifact_dir / filename
        actual_digest = _sha256(path)
        if actual_digest != artifact["sha256"]:
            _fail("RC metadata SHA-256 mismatch for %s" % filename)
        if path.stat().st_size != artifact["size"]:
            _fail("RC metadata size mismatch for %s" % filename)

    verify_distribution_metadata_subset(artifact_dir)
    return metadata


def verify_distribution_metadata_subset(artifact_dir):
    """Inspect distributions from a four-file bundle without weakening file-set checks."""
    artifact_dir = Path(artifact_dir)
    staging = Path(tempfile.mkdtemp(prefix="ruledsl-dist-"))
    try:
        for filename in DISTRIBUTION_FILENAMES:
            shutil.copyfile(str(artifact_dir / filename), str(staging / filename))
        return verify_distribution_metadata(staging)
    finally:
        shutil.rmtree(str(staging), ignore_errors=True)


def _extract_exact_zip(
    archive_path, output_dir, expected_filenames, max_file_bytes, max_total_bytes
):
    archive_path = Path(archive_path)
    output_dir = Path(output_dir)
    _regular_file(archive_path, "artifact ZIP")
    if output_dir.exists():
        _fail("extraction output directory already exists: %s" % output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=output_dir.name + ".", dir=str(output_dir.parent)))
    try:
        with zipfile.ZipFile(str(archive_path), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                _fail("artifact ZIP contains duplicate paths")
            if set(names) != set(expected_filenames):
                _fail("artifact ZIP contains an unexpected file set")
            total_size = 0
            for info in infos:
                name = info.filename
                pure = PurePosixPath(name)
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                if (
                    pure.is_absolute()
                    or len(pure.parts) != 1
                    or pure.name != name
                    or "\\" in name
                    or "\x00" in name
                ):
                    _fail("unsafe artifact ZIP path: %r" % name)
                if stat.S_IFMT(unix_mode) == stat.S_IFLNK or info.is_dir():
                    _fail("artifact ZIP entries must be regular files")
                if info.flag_bits & 0x1:
                    _fail("encrypted artifact ZIP entries are not allowed")
                if info.file_size <= 0 or info.file_size > max_file_bytes:
                    _fail("artifact ZIP entry has an invalid size: %s" % name)
                total_size += info.file_size
                if total_size > max_total_bytes:
                    _fail("artifact ZIP exceeds the uncompressed size limit")
                target = staging / name
                with archive.open(info, "r") as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination, 1024 * 1024)
                if target.stat().st_size != info.file_size:
                    _fail("artifact ZIP extraction size mismatch: %s" % name)
        staging.replace(output_dir)
    except Exception:
        shutil.rmtree(str(staging), ignore_errors=True)
        raise


def extract_bundle_zip(archive_path, output_dir):
    """Safely extract the exact four-file GitHub Actions artifact ZIP."""
    _extract_exact_zip(
        archive_path,
        output_dir,
        BUNDLE_FILENAMES,
        MAX_BUNDLE_FILE_BYTES,
        MAX_BUNDLE_BYTES,
    )


def _self_verify_bundle(artifact_dir):
    artifact_dir = Path(artifact_dir)
    _require_file_set(artifact_dir, BUNDLE_FILENAMES, "RC artifact directory")
    metadata = _load_metadata(artifact_dir / METADATA_FILENAME)
    _validate_metadata_shape(metadata)
    return verify_bundle(
        artifact_dir,
        metadata["source"]["commit_sha"],
        metadata["source"]["tree_hash"],
        metadata["package"]["version"],
        metadata["github_actions"]["run_id"],
        metadata["github_actions"]["run_attempt"],
        metadata["github_actions"]["repository"],
        metadata["github_actions"]["workflow"],
    )


def _artifact_map(metadata):
    return {item["filename"]: item for item in metadata["artifacts"]}


def _validate_testpypi_file_url(url, filename):
    url = _require_string(url, "TestPyPI file URL")
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != TESTPYPI_FILE_HOST
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
        or PurePosixPath(parsed.path).name != filename
    ):
        _fail("unsafe or unexpected TestPyPI file URL for %s" % filename)
    return url


def _validate_registry_file_records(files, metadata, context, exact_keys):
    if not isinstance(files, list) or len(files) != 2:
        _fail("%s must contain exactly the expected wheel and sdist" % context)
    expected_artifacts = _artifact_map(metadata)
    expected_types = {WHEEL_FILENAME: "bdist_wheel", SDIST_FILENAME: "sdist"}
    found = {}
    for index, item in enumerate(files):
        item_context = "%s[%d]" % (context, index)
        if not isinstance(item, dict):
            _fail("%s must be an object" % item_context)
        if exact_keys:
            _require_exact_keys(
                item, ("filename", "packagetype", "sha256", "size", "url"), item_context
            )
        filename = _require_string(item.get("filename"), item_context + ".filename")
        if filename not in expected_artifacts or filename in found:
            _fail("%s has an unexpected or duplicate filename" % context)
        if item.get("packagetype") != expected_types[filename]:
            _fail("%s has an unexpected package type" % filename)
        if exact_keys:
            digest = _require_sha256(item.get("sha256"), item_context + ".sha256")
        else:
            digests = item.get("digests")
            if not isinstance(digests, dict):
                _fail("%s.digests must be an object" % item_context)
            digest = _require_sha256(digests.get("sha256"), item_context + ".digests.sha256")
            if item.get("yanked") is not False:
                _fail("%s must not be yanked" % filename)
        size = item.get("size")
        if type(size) is not int or size <= 0:
            _fail("%s.size must be a positive integer" % item_context)
        artifact = expected_artifacts[filename]
        if digest != artifact["sha256"] or size != artifact["size"]:
            _fail("TestPyPI digest or size differs from RC metadata for %s" % filename)
        url = _validate_testpypi_file_url(item.get("url"), filename)
        found[filename] = {
            "filename": filename,
            "packagetype": expected_types[filename],
            "sha256": digest,
            "size": size,
            "url": url,
        }
    if set(found) != set(DISTRIBUTION_FILENAMES):
        _fail("%s lacks the exact wheel and sdist" % context)
    return [found[filename] for filename in DISTRIBUTION_FILENAMES]


def validate_testpypi_payload(payload, metadata):
    """Validate one TestPyPI version JSON response against RC metadata."""
    if not isinstance(payload, dict):
        _fail("TestPyPI JSON response must be an object")
    info = payload.get("info")
    if not isinstance(info, dict):
        _fail("TestPyPI JSON response lacks package info")
    if info.get("name") != PACKAGE_NAME or info.get("version") != PACKAGE_VERSION:
        _fail("TestPyPI package identity is not ruledsl 1.2.0")
    files = _validate_registry_file_records(
        payload.get("urls"), metadata, "TestPyPI urls", exact_keys=False
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "registry": "testpypi",
        "json_url": TESTPYPI_JSON_URL,
        "package": {"name": PACKAGE_NAME, "version": PACKAGE_VERSION},
        "files": files,
    }


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _fail("registry verification refuses HTTP redirects")


def _open_without_redirects(request, timeout):
    opener = urllib.request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def _fetch_testpypi_json():
    request = urllib.request.Request(
        TESTPYPI_JSON_URL,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "RuleDSL-SDK-release-verifier/1.2.0",
        },
    )
    with _open_without_redirects(request, timeout=20) as response:
        if response.getcode() != 200 or response.geturl() != TESTPYPI_JSON_URL:
            _fail("unexpected TestPyPI JSON response identity")
        content_type = response.headers.get_content_type()
        if content_type != "application/json":
            _fail("TestPyPI JSON endpoint returned %s" % content_type)
        raw = response.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        _fail("TestPyPI JSON response exceeds the size limit")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_json_no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("invalid TestPyPI JSON response: %s" % exc)


def _retry(operation, attempts, delay_seconds, context):
    if type(attempts) is not int or not 1 <= attempts <= 20:
        _fail("retry attempts must be between 1 and 20")
    if type(delay_seconds) is not int or not 0 <= delay_seconds <= 30:
        _fail("retry delay must be between 0 and 30 seconds")
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except (
            ContractError,
            OSError,
            TimeoutError,
            urllib.error.HTTPError,
            urllib.error.URLError,
        ) as exc:
            last_error = exc
            if attempt == attempts:
                break
            print(
                "%s attempt %d/%d failed: %s; retrying in %ds"
                % (context, attempt, attempts, exc, delay_seconds),
                file=sys.stderr,
            )
            time.sleep(delay_seconds)
    _fail("%s failed after %d attempt(s): %s" % (context, attempts, last_error))


def _download_registry_file(entry, destination):
    request = urllib.request.Request(
        entry["url"],
        headers={
            "Accept": "application/octet-stream",
            "Accept-Encoding": "identity",
            "User-Agent": "RuleDSL-SDK-release-verifier/1.2.0",
        },
    )
    digest = hashlib.sha256()
    size = 0
    with _open_without_redirects(request, timeout=30) as response:
        if response.getcode() != 200 or response.geturl() != entry["url"]:
            _fail("unexpected download response for %s" % entry["filename"])
        if response.headers.get("Content-Encoding") not in (None, "identity"):
            _fail("encoded registry downloads are not allowed")
        declared = response.headers.get("Content-Length")
        if declared is not None and declared != str(entry["size"]):
            _fail("registry Content-Length mismatch for %s" % entry["filename"])
        with destination.open("wb") as stream:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > entry["size"]:
                    _fail("registry download exceeds expected size for %s" % entry["filename"])
                digest.update(chunk)
                stream.write(chunk)
    if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
        _fail("downloaded bytes differ from RC metadata for %s" % entry["filename"])


def _validate_registry_evidence(evidence, metadata):
    _require_exact_keys(
        evidence,
        ("schema_version", "registry", "json_url", "package", "files"),
        "TestPyPI registry evidence",
    )
    if type(evidence["schema_version"]) is not int or evidence["schema_version"] != SCHEMA_VERSION:
        _fail("unsupported TestPyPI registry evidence schema")
    if evidence["registry"] != "testpypi" or evidence["json_url"] != TESTPYPI_JSON_URL:
        _fail("unexpected registry evidence identity")
    if evidence["package"] != {"name": PACKAGE_NAME, "version": PACKAGE_VERSION}:
        _fail("unexpected registry evidence package")
    files = _validate_registry_file_records(
        evidence["files"], metadata, "registry evidence files", exact_keys=True
    )
    expected = dict(evidence)
    expected["files"] = files
    if evidence != expected:
        _fail("registry evidence is not canonical")
    return expected


def _validate_registry_directory(registry_dir, metadata):
    registry_dir = Path(registry_dir)
    _require_file_set(
        registry_dir, TESTPYPI_REGISTRY_FILENAMES, "TestPyPI registry directory"
    )
    evidence = _load_json_file(
        registry_dir / TESTPYPI_REGISTRY_FILENAME, "TestPyPI registry evidence"
    )
    evidence = _validate_registry_evidence(evidence, metadata)
    for entry in evidence["files"]:
        path = registry_dir / entry["filename"]
        if path.stat().st_size != entry["size"] or _sha256(path) != entry["sha256"]:
            _fail("local registry download mismatch for %s" % entry["filename"])
    return evidence


def verify_testpypi_registry(artifact_dir, output_dir, attempts, delay_seconds):
    """Query TestPyPI, verify its file records, and download the exact bytes."""
    artifact_dir = Path(artifact_dir)
    output_dir = Path(output_dir)
    metadata = _self_verify_bundle(artifact_dir)
    if output_dir.exists():
        _fail("registry output directory already exists: %s" % output_dir)
    evidence = _retry(
        lambda: validate_testpypi_payload(_fetch_testpypi_json(), metadata),
        attempts,
        delay_seconds,
        "TestPyPI JSON verification",
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=output_dir.name + ".", dir=str(output_dir.parent)))
    try:
        for entry in evidence["files"]:
            destination = staging / entry["filename"]
            _retry(
                lambda entry=entry, destination=destination: _download_registry_file(
                    entry, destination
                ),
                min(attempts, 3),
                delay_seconds,
                "TestPyPI download %s" % entry["filename"],
            )
        with (staging / TESTPYPI_REGISTRY_FILENAME).open(
            "w", encoding="utf-8", newline="\n"
        ) as stream:
            json.dump(evidence, stream, indent=2, sort_keys=True)
            stream.write("\n")
        _validate_registry_directory(staging, metadata)
        staging.replace(output_dir)
    except Exception:
        shutil.rmtree(str(staging), ignore_errors=True)
        raise
    return evidence


def extract_testpypi_receipt_zip(archive_path, output_dir):
    """Safely extract one post-registry-verification TestPyPI receipt."""
    _extract_exact_zip(
        archive_path,
        output_dir,
        (TESTPYPI_RECEIPT_FILENAME,),
        1024 * 1024,
        1024 * 1024,
    )


def _receipt_object(
    metadata,
    registry_files,
    rc_artifact_id,
    publish_run_id,
    publish_run_attempt,
):
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt_type": "testpypi-registry-verification",
        "package": dict(metadata["package"]),
        "rc": {
            "repository": metadata["github_actions"]["repository"],
            "workflow": metadata["github_actions"]["workflow"],
            "run_id": str(metadata["github_actions"]["run_id"]),
            "run_attempt": str(metadata["github_actions"]["run_attempt"]),
            "artifact_id": _require_positive_id(rc_artifact_id, "RC artifact ID"),
            "source_sha": metadata["source"]["commit_sha"],
            "tree_hash": metadata["source"]["tree_hash"],
            "artifacts": list(metadata["artifacts"]),
        },
        "testpypi": {
            "json_url": TESTPYPI_JSON_URL,
            "publish_workflow": PUBLISH_WORKFLOW,
            "publish_run_id": _require_positive_id(
                publish_run_id, "TestPyPI publish run ID"
            ),
            "publish_run_attempt": _require_positive_id(
                publish_run_attempt, "TestPyPI publish run attempt"
            ),
            "files": registry_files,
        },
        "checks": list(TESTPYPI_RECEIPT_CHECKS),
    }


def create_testpypi_receipt(
    artifact_dir,
    registry_dir,
    output_dir,
    rc_artifact_id,
    publish_run_id,
    publish_run_attempt,
):
    """Create a receipt only after the workflow's registry and smoke gates pass."""
    artifact_dir = Path(artifact_dir)
    registry_dir = Path(registry_dir)
    output_dir = Path(output_dir)
    metadata = _self_verify_bundle(artifact_dir)
    evidence = _validate_registry_directory(registry_dir, metadata)
    receipt = _receipt_object(
        metadata,
        evidence["files"],
        rc_artifact_id,
        publish_run_id,
        publish_run_attempt,
    )
    if output_dir.exists():
        _fail("receipt output directory already exists: %s" % output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=output_dir.name + ".", dir=str(output_dir.parent)))
    try:
        with (staging / TESTPYPI_RECEIPT_FILENAME).open(
            "w", encoding="utf-8", newline="\n"
        ) as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
        _require_file_set(
            staging, (TESTPYPI_RECEIPT_FILENAME,), "TestPyPI receipt directory"
        )
        staging.replace(output_dir)
    except Exception:
        shutil.rmtree(str(staging), ignore_errors=True)
        raise
    return receipt


def verify_testpypi_receipt(
    receipt_dir,
    artifact_dir,
    expected_rc_artifact_id,
    expected_publish_run_id,
    expected_publish_run_attempt,
):
    """Require a post-upload registry verification receipt for this exact RC."""
    receipt_dir = Path(receipt_dir)
    artifact_dir = Path(artifact_dir)
    _require_file_set(
        receipt_dir, (TESTPYPI_RECEIPT_FILENAME,), "TestPyPI receipt directory"
    )
    metadata = _self_verify_bundle(artifact_dir)
    receipt = _load_json_file(
        receipt_dir / TESTPYPI_RECEIPT_FILENAME, "TestPyPI verification receipt"
    )
    _require_exact_keys(
        receipt,
        ("schema_version", "receipt_type", "package", "rc", "testpypi", "checks"),
        "TestPyPI verification receipt",
    )
    if type(receipt["schema_version"]) is not int or receipt["schema_version"] != SCHEMA_VERSION:
        _fail("unsupported TestPyPI receipt schema")
    if receipt["receipt_type"] != "testpypi-registry-verification":
        _fail("receipt is not a registry verification receipt")
    if not isinstance(receipt.get("testpypi"), dict):
        _fail("receipt testpypi field must be an object")
    _require_exact_keys(
        receipt["testpypi"],
        ("json_url", "publish_workflow", "publish_run_id", "publish_run_attempt", "files"),
        "receipt testpypi",
    )
    registry_files = _validate_registry_file_records(
        receipt["testpypi"]["files"],
        metadata,
        "receipt TestPyPI files",
        exact_keys=True,
    )
    expected = _receipt_object(
        metadata,
        registry_files,
        expected_rc_artifact_id,
        expected_publish_run_id,
        expected_publish_run_attempt,
    )
    if receipt != expected:
        _fail("TestPyPI verification receipt does not match the selected RC and run")
    return {"metadata": metadata, "receipt": receipt}


def stage_distributions(artifact_dir, output_dir):
    """Copy only verified distribution files into the publisher input directory."""
    artifact_dir = Path(artifact_dir)
    output_dir = Path(output_dir)
    metadata = _self_verify_bundle(artifact_dir)
    artifacts = _artifact_map(metadata)
    if output_dir.exists():
        _fail("publish directory already exists: %s" % output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=output_dir.name + ".", dir=str(output_dir.parent)))
    try:
        for filename in DISTRIBUTION_FILENAMES:
            shutil.copyfile(str(artifact_dir / filename), str(staging / filename))
            if _sha256(staging / filename) != artifacts[filename]["sha256"]:
                _fail("staged distribution hash mismatch: %s" % filename)
            if staging.joinpath(filename).stat().st_size != artifacts[filename]["size"]:
                _fail("staged distribution size mismatch: %s" % filename)
        _require_file_set(staging, DISTRIBUTION_FILENAMES, "publish staging directory")
        verify_distribution_metadata(staging)
        staging.replace(output_dir)
        _require_file_set(output_dir, DISTRIBUTION_FILENAMES, "publish staging directory")
        for filename in DISTRIBUTION_FILENAMES:
            if _sha256(output_dir / filename) != artifacts[filename]["sha256"]:
                _fail("final staged distribution hash mismatch: %s" % filename)
    except Exception:
        shutil.rmtree(str(staging), ignore_errors=True)
        raise


def validate_dispatch(
    target,
    run_id,
    artifact_id,
    testpypi_run_id="",
    production_confirmation="",
):
    if target not in ("testpypi", "pypi"):
        _fail("target must be exactly testpypi or pypi")
    if target == "testpypi":
        if testpypi_run_id:
            _fail("testpypi_run_id must be empty for a TestPyPI publish")
        if production_confirmation:
            _fail("production_confirmation must be empty for a TestPyPI publish")
    else:
        testpypi_run_id = _require_positive_id(
            testpypi_run_id, "TestPyPI publish run ID"
        )
        if production_confirmation != "publish-ruledsl-1.2.0":
            _fail(
                "production_confirmation must be exactly publish-ruledsl-1.2.0"
            )
    return {
        "target": target,
        "run_id": _require_positive_id(run_id, "RC run ID"),
        "artifact_id": _require_positive_id(artifact_id, "RC artifact ID"),
        "testpypi_run_id": testpypi_run_id,
    }


def _add_identity_arguments(parser):
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--expected-tree-hash", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--expected-run-attempt", required=True)
    parser.add_argument("--expected-repository", default=REPOSITORY)
    parser.add_argument("--expected-workflow", default=RC_WORKFLOW)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="create the four-file RC bundle")
    create.add_argument("--dist-dir", required=True)
    create.add_argument("--output-dir", required=True)
    create.add_argument("--source-sha", required=True)
    create.add_argument("--tree-hash", required=True)
    create.add_argument("--run-id", required=True)
    create.add_argument("--run-attempt", required=True)
    create.add_argument("--repository", default=REPOSITORY)
    create.add_argument("--workflow", default=RC_WORKFLOW)

    verify = subparsers.add_parser("verify", help="verify an extracted RC bundle")
    verify.add_argument("--artifact-dir", required=True)
    _add_identity_arguments(verify)

    extract = subparsers.add_parser("extract", help="safely extract an artifact ZIP")
    extract.add_argument("--archive", required=True)
    extract.add_argument("--output-dir", required=True)

    receipt_extract = subparsers.add_parser(
        "extract-testpypi-receipt", help="safely extract a TestPyPI receipt ZIP"
    )
    receipt_extract.add_argument("--archive", required=True)
    receipt_extract.add_argument("--output-dir", required=True)

    receipt_verify = subparsers.add_parser(
        "verify-testpypi-receipt", help="match a TestPyPI receipt to an RC bundle"
    )
    receipt_verify.add_argument("--receipt-dir", required=True)
    receipt_verify.add_argument("--artifact-dir", required=True)
    receipt_verify.add_argument("--expected-rc-artifact-id", required=True)
    receipt_verify.add_argument("--expected-publish-run-id", required=True)
    receipt_verify.add_argument("--expected-publish-run-attempt", required=True)

    registry_verify = subparsers.add_parser(
        "verify-testpypi-registry",
        help="query TestPyPI and download its exact verified distributions",
    )
    registry_verify.add_argument("--artifact-dir", required=True)
    registry_verify.add_argument("--output-dir", required=True)
    registry_verify.add_argument("--attempts", type=int, default=12)
    registry_verify.add_argument("--delay-seconds", type=int, default=10)

    receipt_create = subparsers.add_parser(
        "create-testpypi-receipt",
        help="create the receipt after registry verification and wheel smoke",
    )
    receipt_create.add_argument("--artifact-dir", required=True)
    receipt_create.add_argument("--registry-dir", required=True)
    receipt_create.add_argument("--output-dir", required=True)
    receipt_create.add_argument("--rc-artifact-id", required=True)
    receipt_create.add_argument("--publish-run-id", required=True)
    receipt_create.add_argument("--publish-run-attempt", required=True)

    stage = subparsers.add_parser("stage", help="stage only wheel and sdist for upload")
    stage.add_argument("--artifact-dir", required=True)
    stage.add_argument("--output-dir", required=True)

    dispatch = subparsers.add_parser(
        "validate-dispatch", help="validate workflow_dispatch inputs"
    )
    dispatch.add_argument("--target", required=True)
    dispatch.add_argument("--run-id", required=True)
    dispatch.add_argument("--artifact-id", required=True)
    dispatch.add_argument("--testpypi-run-id", default="")
    dispatch.add_argument("--production-confirmation", default="")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            metadata = create_bundle(
                args.dist_dir,
                args.output_dir,
                args.source_sha,
                args.tree_hash,
                args.run_id,
                args.run_attempt,
                args.repository,
                args.workflow,
            )
            print(json.dumps(metadata, indent=2, sort_keys=True))
        elif args.command == "verify":
            metadata = verify_bundle(
                args.artifact_dir,
                args.expected_source_sha,
                args.expected_tree_hash,
                args.expected_version,
                args.expected_run_id,
                args.expected_run_attempt,
                args.expected_repository,
                args.expected_workflow,
            )
            print(
                "verified RC: source=%s tree=%s version=%s run=%s attempt=%s"
                % (
                    metadata["source"]["commit_sha"],
                    metadata["source"]["tree_hash"],
                    metadata["package"]["version"],
                    metadata["github_actions"]["run_id"],
                    metadata["github_actions"]["run_attempt"],
                )
            )
            for artifact in metadata["artifacts"]:
                print("sha256=%s  %s" % (artifact["sha256"], artifact["filename"]))
        elif args.command == "extract":
            extract_bundle_zip(args.archive, args.output_dir)
            print("safely extracted RC artifact to %s" % args.output_dir)
        elif args.command == "extract-testpypi-receipt":
            extract_testpypi_receipt_zip(args.archive, args.output_dir)
            print("safely extracted TestPyPI receipt to %s" % args.output_dir)
        elif args.command == "verify-testpypi-receipt":
            result = verify_testpypi_receipt(
                args.receipt_dir,
                args.artifact_dir,
                args.expected_rc_artifact_id,
                args.expected_publish_run_id,
                args.expected_publish_run_attempt,
            )
            metadata = result["metadata"]
            print(
                "TestPyPI registry receipt matches RC run=%s source=%s publish_run=%s attempt=%s"
                % (
                    metadata["github_actions"]["run_id"],
                    metadata["source"]["commit_sha"],
                    result["receipt"]["testpypi"]["publish_run_id"],
                    result["receipt"]["testpypi"]["publish_run_attempt"],
                )
            )
        elif args.command == "verify-testpypi-registry":
            evidence = verify_testpypi_registry(
                args.artifact_dir,
                args.output_dir,
                args.attempts,
                args.delay_seconds,
            )
            print("verified TestPyPI JSON and downloaded exact files:")
            for item in evidence["files"]:
                print("sha256=%s  %s" % (item["sha256"], item["filename"]))
        elif args.command == "create-testpypi-receipt":
            receipt = create_testpypi_receipt(
                args.artifact_dir,
                args.registry_dir,
                args.output_dir,
                args.rc_artifact_id,
                args.publish_run_id,
                args.publish_run_attempt,
            )
            print(
                "created post-smoke TestPyPI registry receipt for run=%s attempt=%s"
                % (
                    receipt["testpypi"]["publish_run_id"],
                    receipt["testpypi"]["publish_run_attempt"],
                )
            )
        elif args.command == "stage":
            stage_distributions(args.artifact_dir, args.output_dir)
            print("staged exact wheel and sdist in %s" % args.output_dir)
        elif args.command == "validate-dispatch":
            values = validate_dispatch(
                args.target,
                args.run_id,
                args.artifact_id,
                args.testpypi_run_id,
                args.production_confirmation,
            )
            print(
                "validated dispatch: target=%s run_id=%s artifact_id=%s testpypi_run_id=%s"
                % (
                    values["target"],
                    values["run_id"],
                    values["artifact_id"],
                    values["testpypi_run_id"],
                )
            )
        else:  # pragma: no cover - argparse constrains this value.
            _fail("unknown command")
    except (ContractError, OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print("RC artifact validation failed: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
