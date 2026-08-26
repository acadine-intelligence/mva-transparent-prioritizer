from __future__ import annotations

import hashlib
import json
import stat
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest import mock

from mva_prioritizer.reference_bundle import (
    acquire_reference_artifact,
    load_reference_bundle,
    verify_reference_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


class ReferenceBundleTests(unittest.TestCase):
    def test_checked_in_reference_bundle_is_strict_and_exactly_versioned(self) -> None:
        bundle = load_reference_bundle(ROOT / "config" / "reference-bundle.json")

        self.assertEqual(bundle.bundle_version, "2026-08-26.2")
        self.assertEqual(bundle.assembly, "GRCh38")
        self.assertEqual(bundle.status, "verified")
        self.assertEqual(len(bundle.artifacts), 22)
        self.assertEqual(bundle.pinned_count, 22)
        self.assertEqual(bundle.bootstrap_count, 0)
        expected_pins = {
            "bio-db-hts": "9e249adae396ddbd87c1efd48d8ad8de35d4fbef069d5b0644275514fabd04ba",
            "exomiser-hg38-data": "2ed14f8b63b5612068591648d8c3c6e34ce9d1c66c08a78990597f78031df447",
            "exomiser-phenotype-data": "aa923530ca43cf5051ed2ba7b221bb73deb2b0dd66695b2ba60460db052f0493",
            "vep-cache-human-grch38": "014c7dd9bb5ad06665866d62eb80f31ca761197bcb9b59280300676f996e600d",
            "vep-htslib-source": "f2407df9f97f0bb6b07656579e41a1ca5100464067b6b21bf962a2ea4b0efd65",
        }
        actual_pins = {
            artifact.name: artifact.expected_sha256
            for artifact in bundle.artifacts
            if artifact.name in expected_pins
        }
        self.assertEqual(actual_pins, expected_pins)

    def test_loads_a_strict_exact_https_bundle_manifest(self) -> None:
        payload = self._payload()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bundle.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )

            bundle = load_reference_bundle(path)

        self.assertEqual(bundle.bundle_version, "2026-08-26.2")
        self.assertEqual(bundle.assembly, "GRCh38")
        self.assertEqual(bundle.pinned_count, 1)
        self.assertEqual(bundle.bootstrap_count, 0)
        self.assertEqual(bundle.artifacts[0].name, "tool-source")
        self.assertEqual(bundle.artifacts[0].expected_bytes, 11)

    def test_rejects_mutable_bundle_versions(self) -> None:
        payload = self._payload()
        payload["bundle_version"] = "latest"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bundle.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "invalid_reference_bundle"):
                load_reference_bundle(path)

    def test_verifies_exact_downloaded_bytes_from_a_fully_pinned_bundle(self) -> None:
        content = b"tool-bytes\n"
        payload = self._payload()
        artifact = payload["artifacts"][0]
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = hashlib.sha256(content).hexdigest()
        artifact["source_checksum"] = {
            "algorithm": "sha256",
            "value": hashlib.sha256(content).hexdigest(),
        }
        payload["status"] = "verified"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)
            verified = (
                private
                / "references"
                / bundle.bundle_version
                / "downloads"
                / "verified"
            )
            verified.mkdir(parents=True, mode=0o700)
            artifact_path = verified / bundle.artifacts[0].filename
            artifact_path.write_bytes(content)
            artifact_path.chmod(0o400)

            result = verify_reference_bundle(private, bundle)

        self.assertEqual(result.state, "verified")
        self.assertEqual(result.artifact_count, 1)
        self.assertEqual(result.byte_count, len(content))

    def test_acquires_a_pinned_artifact_into_the_fixed_verified_directory(self) -> None:
        content = b"pinned-tool-bytes\n"
        payload = self._payload()
        artifacts = payload["artifacts"]
        self.assertIsInstance(artifacts, list)
        artifact = artifacts[0]
        self.assertIsInstance(artifact, dict)
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = hashlib.sha256(content).hexdigest()
        artifact["source_checksum"] = {
            "algorithm": "sha256",
            "value": hashlib.sha256(content).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)

            def fake_fetch(_source_url: str, destination: Path, start_byte: int) -> None:
                self.assertEqual(start_byte, 0)
                destination.write_bytes(content)

            result = acquire_reference_artifact(
                private,
                bundle,
                "tool-source",
                fetcher=fake_fetch,
            )
            verified = (
                private
                / "references"
                / bundle.bundle_version
                / "downloads"
                / "verified"
                / bundle.artifacts[0].filename
            )

            self.assertEqual(verified.read_bytes(), content)
            self.assertFalse(verified.with_name(verified.name + ".part").exists())

        self.assertEqual(result.state, "verified")
        self.assertEqual(result.verified_count, 1)
        self.assertEqual(result.pin_required_count, 0)
        self.assertEqual(result.byte_count, len(content))

    def test_rejects_a_symlinked_temporary_acquisition_receipt(self) -> None:
        content = b"pinned-tool-bytes\n"
        payload = self._payload()
        artifact = payload["artifacts"][0]
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = hashlib.sha256(content).hexdigest()
        artifact["source_checksum"] = {
            "algorithm": "sha256",
            "value": hashlib.sha256(content).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)
            receipts = private / "references" / bundle.bundle_version / "receipts"
            receipts.mkdir(parents=True, mode=0o700)
            outside = root / "outside.txt"
            outside.write_text("unchanged\n", encoding="utf-8")
            temporary_receipt = receipts / ".tool-source.json.tmp"
            temporary_receipt.symlink_to(outside)

            def fake_fetch(_source_url: str, destination: Path, start_byte: int) -> None:
                self.assertEqual(start_byte, 0)
                destination.write_bytes(content)

            with self.assertRaisesRegex(ValueError, "unsafe_reference_receipt"):
                acquire_reference_artifact(
                    private,
                    bundle,
                    "tool-source",
                    fetcher=fake_fetch,
                )

            self.assertEqual(outside.read_text(encoding="utf-8"), "unchanged\n")
            self.assertTrue(temporary_receipt.is_symlink())

    def test_rejects_a_fetcher_created_symlink_without_changing_its_target(self) -> None:
        content = b"pinned-tool-bytes\n"
        payload = self._payload()
        artifact = payload["artifacts"][0]
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = hashlib.sha256(content).hexdigest()
        artifact["source_checksum"] = {
            "algorithm": "sha256",
            "value": hashlib.sha256(content).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)
            outside = root / "outside.txt"
            outside.write_bytes(content)
            outside.chmod(0o600)

            def malicious_fetch(_source_url: str, destination: Path, start_byte: int) -> None:
                self.assertEqual(start_byte, 0)
                destination.symlink_to(outside)

            with self.assertRaisesRegex(ValueError, "unsafe_download_candidate"):
                acquire_reference_artifact(
                    private,
                    bundle,
                    "tool-source",
                    fetcher=malicious_fetch,
                )

            self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o600)

    def test_default_fetcher_streams_an_https_response_into_private_quarantine(self) -> None:
        content = b"streamed-tool-bytes\n"
        payload = self._payload()
        artifacts = payload["artifacts"]
        self.assertIsInstance(artifacts, list)
        artifact = artifacts[0]
        self.assertIsInstance(artifact, dict)
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = hashlib.sha256(content).hexdigest()
        artifact["source_checksum"] = {
            "algorithm": "sha256",
            "value": hashlib.sha256(content).hexdigest(),
        }

        class FakeResponse:
            status = 200
            headers = {"Content-Length": str(len(content))}

            def __init__(self) -> None:
                self._stream = BytesIO(content)

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def geturl(self) -> str:
                return artifact["source_url"]

            def read(self, size: int) -> bytes:
                return self._stream.read(size)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)

            with mock.patch(
                "mva_prioritizer.reference_bundle.urlopen",
                return_value=FakeResponse(),
                create=True,
            ) as mocked_urlopen:
                result = acquire_reference_artifact(private, bundle, "tool-source")

        self.assertEqual(result.state, "verified")
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, artifact["source_url"])
        self.assertIsNone(request.get_header("Range"))

    def test_default_fetcher_resumes_from_the_exact_quarantine_byte(self) -> None:
        content = b"resumable-tool-bytes\n"
        split_at = 8
        payload = self._payload()
        artifact = payload["artifacts"][0]
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = hashlib.sha256(content).hexdigest()
        artifact["source_checksum"] = {
            "algorithm": "sha256",
            "value": hashlib.sha256(content).hexdigest(),
        }

        class FakeResponse:
            status = 206
            headers = {
                "Content-Length": str(len(content) - split_at),
                "Content-Range": f"bytes {split_at}-{len(content) - 1}/{len(content)}",
            }

            def __init__(self) -> None:
                self._stream = BytesIO(content[split_at:])

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def geturl(self) -> str:
                return artifact["source_url"]

            def read(self, size: int) -> bytes:
                return self._stream.read(size)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)
            quarantine = (
                private
                / "references"
                / bundle.bundle_version
                / "downloads"
                / "quarantine"
            )
            quarantine.mkdir(parents=True, mode=0o700)
            candidate = quarantine / f"{bundle.artifacts[0].filename}.part"
            candidate.write_bytes(content[:split_at])
            candidate.chmod(0o600)

            with mock.patch(
                "mva_prioritizer.reference_bundle.urlopen",
                return_value=FakeResponse(),
            ) as mocked_urlopen:
                result = acquire_reference_artifact(private, bundle, "tool-source")

            verified = (
                private
                / "references"
                / bundle.bundle_version
                / "downloads"
                / "verified"
                / bundle.artifacts[0].filename
            )
            self.assertEqual(verified.read_bytes(), content)

        self.assertEqual(result.state, "verified")
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Range"), f"bytes={split_at}-")

    def test_digest_mismatch_never_promotes_quarantined_bytes(self) -> None:
        content = b"unexpected-tool-bytes\n"
        payload = self._payload()
        artifact = payload["artifacts"][0]
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = "b" * 64
        artifact["source_checksum"] = {
            "algorithm": "sha256",
            "value": "b" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)

            def fake_fetch(_source_url: str, destination: Path, start_byte: int) -> None:
                self.assertEqual(start_byte, 0)
                destination.write_bytes(content)

            with self.assertRaisesRegex(ValueError, "reference_digest_mismatch"):
                acquire_reference_artifact(
                    private,
                    bundle,
                    "tool-source",
                    fetcher=fake_fetch,
                )

            quarantine = (
                private
                / "references"
                / bundle.bundle_version
                / "downloads"
                / "quarantine"
                / f"{bundle.artifacts[0].filename}.part"
            )
            verified = (
                private
                / "references"
                / bundle.bundle_version
                / "downloads"
                / "verified"
                / bundle.artifacts[0].filename
            )
            self.assertEqual(quarantine.read_bytes(), content)
            self.assertFalse(verified.exists())

    def test_unpinned_artifact_stays_quarantined_and_records_its_sha256(self) -> None:
        content = b"bootstrap-reference-bytes\n"
        payload = self._payload()
        artifact = payload["artifacts"][0]
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = None
        artifact["source_checksum"] = {"algorithm": "none", "value": None}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)

            def fake_fetch(_source_url: str, destination: Path, start_byte: int) -> None:
                self.assertEqual(start_byte, 0)
                destination.write_bytes(content)

            result = acquire_reference_artifact(
                private,
                bundle,
                "tool-source",
                fetcher=fake_fetch,
            )

            quarantine = (
                private
                / "references"
                / bundle.bundle_version
                / "downloads"
                / "quarantine"
                / f"{bundle.artifacts[0].filename}.part"
            )
            verified = (
                private
                / "references"
                / bundle.bundle_version
                / "downloads"
                / "verified"
                / bundle.artifacts[0].filename
            )
            receipt = (
                private
                / "references"
                / bundle.bundle_version
                / "receipts"
                / "tool-source.json"
            )
            receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(quarantine.read_bytes(), content)
            self.assertFalse(verified.exists())
            self.assertEqual(receipt_payload["state"], "pin_required")
            self.assertEqual(
                receipt_payload["measured_sha256"],
                hashlib.sha256(content).hexdigest(),
            )

        self.assertEqual(result.state, "pin_required")
        self.assertEqual(result.verified_count, 0)
        self.assertEqual(result.pin_required_count, 1)

    def test_pinned_manifest_promotes_complete_quarantine_without_redownload(self) -> None:
        content = b"locally-frozen-reference-bytes\n"
        payload = self._payload()
        artifact = payload["artifacts"][0]
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = None
        artifact["source_checksum"] = {"algorithm": "none", "value": None}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bootstrap_bundle = load_reference_bundle(manifest)

            def fake_fetch(_source_url: str, destination: Path, start_byte: int) -> None:
                self.assertEqual(start_byte, 0)
                destination.write_bytes(content)

            first = acquire_reference_artifact(
                private,
                bootstrap_bundle,
                "tool-source",
                fetcher=fake_fetch,
            )
            self.assertEqual(first.state, "pin_required")

            artifact["expected_sha256"] = first.measured_sha256
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            pinned_bundle = load_reference_bundle(manifest)

            def forbidden_fetch(_source_url: str, _destination: Path, _start_byte: int) -> None:
                self.fail("complete quarantine must be promoted without a network fetch")

            second = acquire_reference_artifact(
                private,
                pinned_bundle,
                "tool-source",
                fetcher=forbidden_fetch,
            )

            verified = (
                private
                / "references"
                / pinned_bundle.bundle_version
                / "downloads"
                / "verified"
                / pinned_bundle.artifacts[0].filename
            )
            quarantine = verified.parent.parent / "quarantine" / f"{verified.name}.part"
            self.assertEqual(verified.read_bytes(), content)
            self.assertFalse(quarantine.exists())

        self.assertEqual(second.state, "verified")
        self.assertEqual(second.verified_count, 1)

    def test_provider_md5_mismatch_blocks_local_sha_freeze(self) -> None:
        content = b"provider-checked-reference-bytes\n"
        payload = self._payload()
        artifact = payload["artifacts"][0]
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = None
        artifact["source_checksum"] = {
            "algorithm": "md5",
            "value": "0" * 32,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)

            def fake_fetch(_source_url: str, destination: Path, start_byte: int) -> None:
                self.assertEqual(start_byte, 0)
                destination.write_bytes(content)

            with self.assertRaisesRegex(ValueError, "source_checksum_mismatch"):
                acquire_reference_artifact(
                    private,
                    bundle,
                    "tool-source",
                    fetcher=fake_fetch,
                )

            verified = (
                private
                / "references"
                / bundle.bundle_version
                / "downloads"
                / "verified"
                / bundle.artifacts[0].filename
            )
            receipt = (
                private
                / "references"
                / bundle.bundle_version
                / "receipts"
                / "tool-source.json"
            )
            self.assertFalse(verified.exists())
            self.assertFalse(receipt.exists())

    def test_provider_md5_match_allows_local_sha_freeze(self) -> None:
        content = b"provider-checked-reference-bytes\n"
        payload = self._payload()
        artifact = payload["artifacts"][0]
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = None
        artifact["source_checksum"] = {
            "algorithm": "md5",
            "value": hashlib.md5(content).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)

            def fake_fetch(_source_url: str, destination: Path, start_byte: int) -> None:
                self.assertEqual(start_byte, 0)
                destination.write_bytes(content)

            result = acquire_reference_artifact(
                private,
                bundle,
                "tool-source",
                fetcher=fake_fetch,
            )

        self.assertEqual(result.state, "pin_required")
        self.assertEqual(result.measured_sha256, hashlib.sha256(content).hexdigest())

    def test_rejects_an_unimplemented_posix_checksum_contract(self) -> None:
        payload = self._payload()
        payload["artifacts"][0]["source_checksum"] = {
            "algorithm": "posix-cksum",
            "value": "1234567890",
        }
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "invalid_reference_bundle"):
                load_reference_bundle(manifest)

    def test_default_fetcher_rejects_an_unapproved_redirect_host(self) -> None:
        content = b"redirected-source-archive\n"
        payload = self._payload()
        artifact = payload["artifacts"][0]
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = hashlib.sha256(content).hexdigest()
        artifact["source_checksum"] = {
            "algorithm": "sha256",
            "value": hashlib.sha256(content).hexdigest(),
        }

        class FakeResponse:
            status = 200
            headers = {"Content-Length": str(len(content))}

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def geturl(self) -> str:
                return "https://unapproved.example/tool-1.0.tar.gz"

            def read(self, size: int) -> bytes:
                return content[:size]

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)

            with (
                mock.patch(
                    "mva_prioritizer.reference_bundle.urlopen",
                    return_value=FakeResponse(),
                ),
                self.assertRaisesRegex(ValueError, "reference_download_redirect_rejected"),
            ):
                acquire_reference_artifact(private, bundle, "tool-source")

            candidate = (
                private
                / "references"
                / bundle.bundle_version
                / "downloads"
                / "quarantine"
                / f"{bundle.artifacts[0].filename}.part"
            )
            self.assertFalse(candidate.exists())

    def test_default_fetcher_accepts_the_pinned_github_codeload_redirect(self) -> None:
        content = b"pinned-source-archive\n"
        payload = self._payload()
        artifact = payload["artifacts"][0]
        artifact["expected_bytes"] = len(content)
        artifact["expected_sha256"] = hashlib.sha256(content).hexdigest()
        artifact["source_checksum"] = {
            "algorithm": "sha256",
            "value": hashlib.sha256(content).hexdigest(),
        }
        artifact["filename"] = "97c24b205f4ba8b44ccc75b839512a1d59104019.tar.gz"
        artifact["source_url"] = (
            "https://github.com/Ensembl/ensembl-vep/archive/"
            "97c24b205f4ba8b44ccc75b839512a1d59104019.tar.gz"
        )

        class FakeResponse:
            status = 200
            headers = {"Content-Length": str(len(content))}

            def __init__(self) -> None:
                self._stream = BytesIO(content)

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def geturl(self) -> str:
                return (
                    "https://codeload.github.com/Ensembl/ensembl-vep/tar.gz/"
                    "97c24b205f4ba8b44ccc75b839512a1d59104019"
                )

            def read(self, size: int) -> bytes:
                return self._stream.read(size)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            manifest = root / "bundle.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = load_reference_bundle(manifest)

            with mock.patch(
                "mva_prioritizer.reference_bundle.urlopen",
                return_value=FakeResponse(),
            ):
                result = acquire_reference_artifact(private, bundle, "tool-source")

        self.assertEqual(result.state, "verified")

    def _payload(self) -> dict[str, Any]:
        return {
            "artifacts": [
                {
                    "expected_bytes": 11,
                    "expected_sha256": "a" * 64,
                    "filename": "tool-1.0.tar.gz",
                    "install_kind": "source-tar",
                    "name": "tool-source",
                    "role": "tool_source",
                    "source_checksum": {"algorithm": "sha256", "value": "a" * 64},
                    "source_url": "https://github.com/example/project/releases/download/1.0/tool-1.0.tar.gz",
                    "version": "1.0",
                }
            ],
            "assembly": "GRCh38",
            "bundle_version": "2026-08-26.2",
            "fastq_included": False,
            "network_during_private_run": False,
            "private_runtime": "m1-encrypted-workspace",
            "protected_data_allowed_on_public_compute": False,
            "schema_version": 2,
            "status": "declared",
        }


if __name__ == "__main__":
    unittest.main()
