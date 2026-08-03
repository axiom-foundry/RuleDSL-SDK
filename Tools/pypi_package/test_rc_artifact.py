"""Fail-closed tests for the PyPI RC artifact contract."""

import io
import json
import shutil
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import rc_artifact


SOURCE_SHA = "1" * 40
TREE_HASH = "2" * 40
RUN_ID = "123456789"
RUN_ATTEMPT = "1"


class RcArtifactContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="ruledsl-rc-test-"))
        self.dist = self.temp / "dist"
        self.dist.mkdir()
        self._write_wheel()
        self._write_sdist()
        self.bundle = self.temp / "bundle"
        rc_artifact.create_bundle(
            self.dist,
            self.bundle,
            SOURCE_SHA,
            TREE_HASH,
            RUN_ID,
            RUN_ATTEMPT,
        )

    def tearDown(self):
        shutil.rmtree(str(self.temp), ignore_errors=True)

    @staticmethod
    def _package_metadata():
        return (
            "Metadata-Version: 2.1\n"
            "Name: ruledsl\n"
            "Version: 1.2.0\n"
            "Requires-Python: >=3.7\n\n"
        ).encode("ascii")

    def _write_wheel(self):
        path = self.dist / rc_artifact.WHEEL_FILENAME
        with zipfile.ZipFile(str(path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "ruledsl-1.2.0.dist-info/METADATA", self._package_metadata()
            )
            archive.writestr(
                "ruledsl-1.2.0.dist-info/WHEEL",
                "Wheel-Version: 1.0\n"
                "Generator: contract-test\n"
                "Root-Is-Purelib: true\n"
                "Tag: py3-none-any\n\n",
            )
            archive.writestr("ruledsl/__init__.py", "# fixture\n")

    def _write_sdist(self):
        path = self.dist / rc_artifact.SDIST_FILENAME
        payload = self._package_metadata()
        with tarfile.open(str(path), "w:gz") as archive:
            info = tarfile.TarInfo("ruledsl-1.2.0/PKG-INFO")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))

    def _verify(self, **overrides):
        values = {
            "expected_source_sha": SOURCE_SHA,
            "expected_tree_hash": TREE_HASH,
            "expected_version": rc_artifact.PACKAGE_VERSION,
            "expected_run_id": RUN_ID,
            "expected_run_attempt": RUN_ATTEMPT,
            "expected_repository": rc_artifact.REPOSITORY,
            "expected_workflow": rc_artifact.RC_WORKFLOW,
        }
        values.update(overrides)
        return rc_artifact.verify_bundle(self.bundle, **values)

    def _testpypi_payload(self):
        metadata = self._verify()
        artifacts = {
            item["filename"]: item for item in metadata["artifacts"]
        }
        return {
            "info": {"name": "ruledsl", "version": "1.2.0"},
            "urls": [
                {
                    "filename": filename,
                    "packagetype": package_type,
                    "digests": {"sha256": artifacts[filename]["sha256"]},
                    "size": artifacts[filename]["size"],
                    "url": (
                        "https://test-files.pythonhosted.org/packages/fixture/"
                        + filename
                    ),
                    "yanked": False,
                }
                for filename, package_type in (
                    (rc_artifact.WHEEL_FILENAME, "bdist_wheel"),
                    (rc_artifact.SDIST_FILENAME, "sdist"),
                )
            ],
        }

    def _registry_directory(self):
        evidence = rc_artifact.validate_testpypi_payload(
            self._testpypi_payload(), self._verify()
        )
        registry = self.temp / "registry"
        registry.mkdir()
        for filename in rc_artifact.DISTRIBUTION_FILENAMES:
            shutil.copyfile(str(self.bundle / filename), str(registry / filename))
        (registry / rc_artifact.TESTPYPI_REGISTRY_FILENAME).write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return registry

    def test_valid_bundle_and_safe_zip_round_trip(self):
        metadata = self._verify()
        self.assertEqual(metadata["package"]["version"], "1.2.0")
        archive_path = self.temp / "artifact.zip"
        with zipfile.ZipFile(str(archive_path), "w") as archive:
            for path in self.bundle.iterdir():
                archive.write(str(path), path.name)
        extracted = self.temp / "extracted"
        rc_artifact.extract_bundle_zip(archive_path, extracted)
        self.bundle = extracted
        self._verify()

        publish = self.temp / "workspace-publish-dist"
        rc_artifact.stage_distributions(self.bundle, publish)
        self.assertEqual(
            {path.name for path in publish.iterdir()},
            set(rc_artifact.DISTRIBUTION_FILENAMES),
        )
        artifact_hashes = {
            item["filename"]: item["sha256"] for item in metadata["artifacts"]
        }
        for filename in rc_artifact.DISTRIBUTION_FILENAMES:
            self.assertEqual(
                rc_artifact._sha256(publish / filename), artifact_hashes[filename]
            )

    def test_publish_staging_must_not_preexist(self):
        publish = self.temp / "workspace-publish-dist"
        publish.mkdir()
        with self.assertRaisesRegex(rc_artifact.ContractError, "already exists"):
            rc_artifact.stage_distributions(self.bundle, publish)

    def test_changed_artifact_byte_is_rejected(self):
        wheel = self.bundle / rc_artifact.WHEEL_FILENAME
        with wheel.open("ab") as stream:
            stream.write(b"tampered")
        with self.assertRaisesRegex(rc_artifact.ContractError, "SHA256SUMS mismatch"):
            self._verify()
        with self.assertRaisesRegex(rc_artifact.ContractError, "SHA256SUMS mismatch"):
            rc_artifact.stage_distributions(self.bundle, self.temp / "publish")

    def test_wrong_release_identities_are_rejected(self):
        cases = (
            {"expected_source_sha": "3" * 40},
            {"expected_tree_hash": "4" * 40},
            {"expected_version": "1.2.1"},
            {"expected_run_id": "987654321"},
            {"expected_run_attempt": "2"},
            {"expected_repository": "attacker/RuleDSL-SDK"},
            {"expected_workflow": ".github/workflows/other.yml"},
        )
        for override in cases:
            with self.subTest(override=override):
                with self.assertRaises(rc_artifact.ContractError):
                    self._verify(**override)

    def test_metadata_change_even_with_valid_json_is_rejected(self):
        path = self.bundle / rc_artifact.METADATA_FILENAME
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["source"]["commit_sha"] = "5" * 40
        path.write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaisesRegex(rc_artifact.ContractError, "RC identity mismatch"):
            self._verify()

    def test_extra_bundle_file_is_rejected(self):
        (self.bundle / "unexpected.txt").write_text("no", encoding="ascii")
        with self.assertRaisesRegex(rc_artifact.ContractError, "file set differs"):
            self._verify()

    def test_unsafe_zip_path_is_rejected_without_escape(self):
        archive_path = self.temp / "unsafe.zip"
        with zipfile.ZipFile(str(archive_path), "w") as archive:
            archive.writestr("../escaped", "no")
            for path in self.bundle.iterdir():
                archive.write(str(path), path.name)
        output = self.temp / "unsafe-output"
        with self.assertRaisesRegex(rc_artifact.ContractError, "unexpected file set"):
            rc_artifact.extract_bundle_zip(archive_path, output)
        self.assertFalse((self.temp / "escaped").exists())

    def test_registry_json_requires_exact_rc_file_set_and_hashes(self):
        metadata = self._verify()
        evidence = rc_artifact.validate_testpypi_payload(
            self._testpypi_payload(), metadata
        )
        self.assertEqual(
            [item["filename"] for item in evidence["files"]],
            list(rc_artifact.DISTRIBUTION_FILENAMES),
        )

        cases = []
        extra = self._testpypi_payload()
        extra["urls"].append(dict(extra["urls"][0], filename="unexpected.whl"))
        cases.append(extra)
        digest = self._testpypi_payload()
        digest["urls"][0]["digests"]["sha256"] = "f" * 64
        cases.append(digest)
        unsafe_url = self._testpypi_payload()
        unsafe_url["urls"][0]["url"] = "https://example.com/" + rc_artifact.WHEEL_FILENAME
        cases.append(unsafe_url)
        yanked = self._testpypi_payload()
        yanked["urls"][0]["yanked"] = True
        cases.append(yanked)
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(rc_artifact.ContractError):
                    rc_artifact.validate_testpypi_payload(payload, metadata)

    def test_registry_verification_downloads_and_rechecks_exact_bytes(self):
        payload = self._testpypi_payload()
        registry = self.temp / "registry-download"

        def copy_download(entry, destination):
            shutil.copyfile(
                str(self.bundle / entry["filename"]), str(destination)
            )

        with mock.patch.object(
            rc_artifact, "_fetch_testpypi_json", return_value=payload
        ), mock.patch.object(
            rc_artifact, "_download_registry_file", side_effect=copy_download
        ):
            evidence = rc_artifact.verify_testpypi_registry(
                self.bundle, registry, 3, 0
            )

        self.assertEqual(
            {path.name for path in registry.iterdir()},
            set(rc_artifact.TESTPYPI_REGISTRY_FILENAMES),
        )
        self.assertEqual(
            evidence,
            json.loads(
                (registry / rc_artifact.TESTPYPI_REGISTRY_FILENAME).read_text(
                    encoding="utf-8"
                )
            ),
        )

    def test_post_registry_receipt_round_trip_and_identity(self):
        registry = self._registry_directory()
        receipt_source = self.temp / "receipt-source"
        receipt = rc_artifact.create_testpypi_receipt(
            self.bundle, registry, receipt_source, "456", "789", "2"
        )
        self.assertEqual(receipt["receipt_type"], "testpypi-registry-verification")
        self.assertEqual(receipt["checks"], list(rc_artifact.TESTPYPI_RECEIPT_CHECKS))

        receipt_zip = self.temp / "receipt.zip"
        with zipfile.ZipFile(str(receipt_zip), "w") as archive:
            archive.write(
                str(receipt_source / rc_artifact.TESTPYPI_RECEIPT_FILENAME),
                rc_artifact.TESTPYPI_RECEIPT_FILENAME,
            )
        receipt_dir = self.temp / "receipt"
        rc_artifact.extract_testpypi_receipt_zip(receipt_zip, receipt_dir)
        rc_artifact.verify_testpypi_receipt(
            receipt_dir, self.bundle, "456", "789", "2"
        )

        with self.assertRaisesRegex(rc_artifact.ContractError, "does not match"):
            rc_artifact.verify_testpypi_receipt(
                receipt_dir, self.bundle, "456", "789", "3"
            )

        receipt_path = receipt_dir / rc_artifact.TESTPYPI_RECEIPT_FILENAME
        changed = json.loads(receipt_path.read_text(encoding="utf-8"))
        changed["checks"].remove("console-help")
        receipt_path.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(rc_artifact.ContractError, "does not match"):
            rc_artifact.verify_testpypi_receipt(
                receipt_dir, self.bundle, "456", "789", "2"
            )

    def test_metadata_copy_is_not_a_registry_receipt(self):
        receipt_dir = self.temp / "old-receipt"
        receipt_dir.mkdir()
        shutil.copyfile(
            str(self.bundle / rc_artifact.METADATA_FILENAME),
            str(receipt_dir / rc_artifact.TESTPYPI_RECEIPT_FILENAME),
        )
        with self.assertRaisesRegex(rc_artifact.ContractError, "keys differ"):
            rc_artifact.verify_testpypi_receipt(
                receipt_dir, self.bundle, "456", "789", "2"
            )

    def test_receipt_rejects_tampered_registry_download(self):
        registry = self._registry_directory()
        with (registry / rc_artifact.WHEEL_FILENAME).open("ab") as stream:
            stream.write(b"tampered")
        with self.assertRaisesRegex(rc_artifact.ContractError, "local registry download"):
            rc_artifact.create_testpypi_receipt(
                self.bundle,
                registry,
                self.temp / "receipt-source",
                "456",
                "789",
                "2",
            )

    def test_registry_retry_is_bounded(self):
        calls = []

        def fail():
            calls.append(1)
            raise rc_artifact.ContractError("not visible yet")

        with self.assertRaisesRegex(rc_artifact.ContractError, "after 3 attempt"):
            rc_artifact._retry(fail, 3, 0, "registry")
        self.assertEqual(len(calls), 3)

    def test_publish_workflow_encodes_post_registry_contract(self):
        repository = Path(__file__).resolve().parents[2]
        workflow = (
            repository / ".github" / "workflows" / "pypi-publish.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(workflow.count("packages-dir: pypi-publish-dist"), 2)
        self.assertNotIn("packages-dir: ${{ runner.temp }}", workflow)
        self.assertIn(
            'PUBLISH_DIR="$GITHUB_WORKSPACE/pypi-publish-dist"', workflow
        )
        upload = workflow.index("- name: Publish to TestPyPI")
        verify_job = workflow.index("  verify-testpypi:")
        no_oidc = workflow.index("      id-token: none", verify_job)
        smoke = workflow.index(
            "- name: Install the downloaded wheel in a clean venv", verify_job
        )
        receipt = workflow.index(
            "- name: Create the post-verification receipt", verify_job
        )
        receipt_upload = workflow.index(
            "- name: Upload the successful registry verification receipt",
            verify_job,
        )
        self.assertLess(upload, verify_job)
        self.assertLess(verify_job, no_oidc)
        self.assertLess(no_oidc, smoke)
        self.assertLess(smoke, receipt)
        self.assertLess(receipt, receipt_upload)
        self.assertNotIn(
            "path: ${{ runner.temp }}/rc-artifact/RC_METADATA.json", workflow
        )

    def test_dispatch_inputs_are_closed(self):
        self.assertEqual(
            rc_artifact.validate_dispatch("testpypi", RUN_ID, "456")["target"],
            "testpypi",
        )
        self.assertEqual(
            rc_artifact.validate_dispatch(
                "pypi", RUN_ID, "456", "789", "publish-ruledsl-1.2.0"
            )["target"],
            "pypi",
        )
        for target, run_id, artifact_id, test_run, confirmation in (
            ("production", RUN_ID, "456", "", ""),
            ("testpypi; echo unsafe", RUN_ID, "456", "", ""),
            ("testpypi", RUN_ID, "456", "789", ""),
            ("pypi", "0", "456", "789", "publish-ruledsl-1.2.0"),
            ("pypi", "-1", "456", "789", "publish-ruledsl-1.2.0"),
            ("pypi", "1; echo unsafe", "456", "789", "publish-ruledsl-1.2.0"),
            ("pypi", RUN_ID, "../456", "789", "publish-ruledsl-1.2.0"),
            ("pypi", RUN_ID, "456", "", "publish-ruledsl-1.2.0"),
            ("pypi", RUN_ID, "456", "789", "yes"),
        ):
            with self.subTest(
                target=target, run_id=run_id, artifact_id=artifact_id
                ):
                with self.assertRaises(rc_artifact.ContractError):
                    rc_artifact.validate_dispatch(
                        target, run_id, artifact_id, test_run, confirmation
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
