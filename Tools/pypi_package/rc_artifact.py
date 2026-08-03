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
TESTPYPI_RECEIPT_FILENAME = METADATA_FILENAME
REPOSITORY = "axiom-foundry/RuleDSL-SDK"
RC_WORKFLOW = ".github/workflows/pypi-rc-build.yml"
PUBLISH_WORKFLOW = ".github/workflows/pypi-publish.yml"
SCHEMA_VERSION = 1

DISTRIBUTION_FILENAMES = (WHEEL_FILENAME, SDIST_FILENAME)
BUNDLE_FILENAMES = frozenset(
    (WHEEL_FILENAME, SDIST_FILENAME, METADATA_FILENAME, CHECKSUM_FILENAME)
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


def _load_metadata(path):
    _regular_file(path, "RC metadata")
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream, object_pairs_hook=_json_no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("invalid RC_METADATA.json: %s" % exc)


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


def extract_testpypi_receipt_zip(archive_path, output_dir):
    """Safely extract a TestPyPI receipt containing only RC_METADATA.json."""
    _extract_exact_zip(
        archive_path,
        output_dir,
        (TESTPYPI_RECEIPT_FILENAME,),
        1024 * 1024,
        1024 * 1024,
    )


def verify_testpypi_receipt(receipt_dir, artifact_dir):
    """Prove the prior TestPyPI run recorded this exact RC metadata file."""
    receipt_dir = Path(receipt_dir)
    artifact_dir = Path(artifact_dir)
    _require_file_set(
        receipt_dir, (TESTPYPI_RECEIPT_FILENAME,), "TestPyPI receipt directory"
    )
    _require_file_set(artifact_dir, BUNDLE_FILENAMES, "RC artifact directory")
    receipt_path = receipt_dir / TESTPYPI_RECEIPT_FILENAME
    artifact_path = artifact_dir / METADATA_FILENAME
    receipt_metadata = _load_metadata(receipt_path)
    artifact_metadata = _load_metadata(artifact_path)
    _validate_metadata_shape(receipt_metadata)
    _validate_metadata_shape(artifact_metadata)
    if _sha256(receipt_path) != _sha256(artifact_path):
        _fail("TestPyPI receipt does not match the selected RC metadata bytes")
    return artifact_metadata


def stage_distributions(artifact_dir, output_dir):
    """Copy only verified distribution files into the publisher input directory."""
    artifact_dir = Path(artifact_dir)
    output_dir = Path(output_dir)
    _require_file_set(artifact_dir, BUNDLE_FILENAMES, "RC artifact directory")
    metadata = _load_metadata(artifact_dir / METADATA_FILENAME)
    _validate_metadata_shape(metadata)
    metadata = verify_bundle(
        artifact_dir,
        metadata["source"]["commit_sha"],
        metadata["source"]["tree_hash"],
        metadata["package"]["version"],
        metadata["github_actions"]["run_id"],
        metadata["github_actions"]["run_attempt"],
        metadata["github_actions"]["repository"],
        metadata["github_actions"]["workflow"],
    )
    artifacts = {item["filename"]: item for item in metadata["artifacts"]}
    if output_dir.exists():
        _fail("publish directory already exists: %s" % output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=output_dir.name + ".", dir=str(output_dir.parent)))
    try:
        for filename in DISTRIBUTION_FILENAMES:
            shutil.copyfile(str(artifact_dir / filename), str(staging / filename))
            if _sha256(staging / filename) != artifacts[filename]["sha256"]:
                _fail("staged distribution hash mismatch: %s" % filename)
        staging.replace(output_dir)
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
            metadata = verify_testpypi_receipt(args.receipt_dir, args.artifact_dir)
            print(
                "TestPyPI receipt matches RC run=%s source=%s"
                % (
                    metadata["github_actions"]["run_id"],
                    metadata["source"]["commit_sha"],
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
