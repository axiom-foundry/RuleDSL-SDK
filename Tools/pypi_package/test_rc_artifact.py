"""Fail-closed tests for the PyPI RC artifact contract."""

import io
import json
import shutil
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

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

    def test_testpypi_receipt_must_match_exact_metadata_bytes(self):
        receipt_zip = self.temp / "receipt.zip"
        with zipfile.ZipFile(str(receipt_zip), "w") as archive:
            archive.write(
                str(self.bundle / rc_artifact.METADATA_FILENAME),
                rc_artifact.TESTPYPI_RECEIPT_FILENAME,
            )
        receipt_dir = self.temp / "receipt"
        rc_artifact.extract_testpypi_receipt_zip(receipt_zip, receipt_dir)
        rc_artifact.verify_testpypi_receipt(receipt_dir, self.bundle)

        receipt_path = receipt_dir / rc_artifact.TESTPYPI_RECEIPT_FILENAME
        metadata = json.loads(receipt_path.read_text(encoding="utf-8"))
        metadata["source"]["commit_sha"] = "6" * 40
        receipt_path.write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaisesRegex(rc_artifact.ContractError, "does not match"):
            rc_artifact.verify_testpypi_receipt(receipt_dir, self.bundle)

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
