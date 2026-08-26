from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mva_prioritizer.manifest import validate_manifest


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.private = Path(self.temporary.name).resolve() / "controlled"
        self.private.mkdir(mode=0o700)
        data = self.private / "data"
        data.mkdir(mode=0o700)
        self.input_bytes = b'{"synthetic":true,"records":2}\n'
        self.input_path = data / "synthetic-input.json"
        self.input_path.write_bytes(self.input_bytes)
        self.input_path.chmod(0o400)
        self.manifest_path = self.private / "manifest.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_validates_exact_bytes_from_a_synthetic_manifest(self) -> None:
        manifest = self._manifest()
        self._write_manifest(manifest)

        result = validate_manifest(self.private, "manifest.json", expected_run_kind="synthetic")

        self.assertEqual(result.state, "validated")
        self.assertEqual(result.run_kind, "synthetic")
        self.assertEqual(result.artifact_count, 1)
        self.assertEqual(result.sample_count, 1)
        self.assertEqual(result.manifest_sha256, hashlib.sha256(self.manifest_path.read_bytes()).hexdigest())

    def test_rejects_an_input_changed_after_manifest_freeze(self) -> None:
        self._write_manifest(self._manifest())
        self.input_path.chmod(0o600)
        self.input_path.write_bytes(self.input_bytes.replace(b"records\":2", b"records\":3"))
        self.input_path.chmod(0o400)

        with self.assertRaisesRegex(ValueError, "stale_receipt"):
            validate_manifest(self.private, "manifest.json", expected_run_kind="synthetic")

    def test_rejects_unknown_manifest_fields_without_reflecting_their_values(self) -> None:
        manifest = self._manifest()
        manifest["sample_name"] = "SYNTHETIC_CANARY_DO_NOT_REFLECT"
        self._write_manifest(manifest)

        with self.assertRaises(ValueError) as captured:
            validate_manifest(self.private, "manifest.json", expected_run_kind="synthetic")

        self.assertEqual(str(captured.exception), "invalid_manifest")
        self.assertNotIn("SYNTHETIC_CANARY", str(captured.exception))

    def test_rejects_artifact_fields_that_can_widen_custody(self) -> None:
        manifest = self._manifest()
        manifest["artifacts"][0]["external_url"] = "https://example.invalid/private"
        self._write_manifest(manifest)

        with self.assertRaisesRegex(ValueError, "invalid_manifest"):
            validate_manifest(self.private, "manifest.json", expected_run_kind="synthetic")

    def test_rejects_duplicate_artifact_identity(self) -> None:
        manifest = self._manifest()
        manifest["artifacts"].append(dict(manifest["artifacts"][0]))
        self._write_manifest(manifest)

        with self.assertRaisesRegex(ValueError, "invalid_manifest"):
            validate_manifest(self.private, "manifest.json", expected_run_kind="synthetic")

    def test_rejects_malformed_contracts_before_artifact_processing(self) -> None:
        malformed: list[dict[str, object]] = []
        for field, value in (
            ("schema_version", 2),
            ("assembly", "GRCh37"),
            ("sample_count", 0),
        ):
            manifest = self._manifest()
            manifest[field] = value
            malformed.append(manifest)

        for field, value in (
            ("bytes", True),
            ("sha256", "A" * 64),
            ("name", "../artifact"),
            ("class", "upload"),
            ("privacy_class", "controlled"),
        ):
            manifest = self._manifest()
            manifest["artifacts"][0][field] = value
            malformed.append(manifest)

        tool_extra = self._manifest()
        tool_extra["tools"][0]["path"] = "/usr/bin/python3"
        malformed.append(tool_extra)

        duplicate_tool = self._manifest()
        duplicate_tool["tools"].append(copy.deepcopy(duplicate_tool["tools"][0]))
        malformed.append(duplicate_tool)

        for index, manifest in enumerate(malformed):
            with self.subTest(index=index):
                self._write_manifest(manifest)
                with self.assertRaises(ValueError) as captured:
                    validate_manifest(self.private, "manifest.json", expected_run_kind="synthetic")
                self.assertEqual(str(captured.exception), "invalid_manifest")

    def test_rejects_duplicate_json_keys(self) -> None:
        raw = json.dumps(self._manifest(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        raw = raw.replace("{\"artifacts\"", "{\"schema_version\":1,\"artifacts\"", 1)
        self.manifest_path.write_text(raw + "\n", encoding="utf-8")
        self.manifest_path.chmod(0o400)

        with self.assertRaisesRegex(ValueError, "invalid_manifest"):
            validate_manifest(self.private, "manifest.json", expected_run_kind="synthetic")

    def _manifest(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "run_kind": "synthetic",
            "assembly": "GRCh38",
            "sample_count": 1,
            "artifacts": [
                {
                    "name": "synthetic-input",
                    "class": "input",
                    "privacy_class": "synthetic",
                    "relative_path": "data/synthetic-input.json",
                    "format": "json",
                    "bytes": len(self.input_bytes),
                    "sha256": hashlib.sha256(self.input_bytes).hexdigest(),
                }
            ],
            "tools": [
                {
                    "name": "python",
                    "version": "3.9+",
                    "binary_sha256": "0" * 64,
                }
            ],
        }

    def _write_manifest(self, manifest: dict[str, object]) -> None:
        if self.manifest_path.exists():
            self.manifest_path.chmod(0o600)
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.manifest_path.chmod(0o400)


if __name__ == "__main__":
    unittest.main()
