from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mva_prioritizer.environment import (
    SUPPORT_PATHS,
    SUPPORT_VERSIONS,
    SystemState,
    TOOL_PATHS,
    verify_environment,
)
from mva_prioritizer.reference_bundle import load_reference_bundle
from mva_prioritizer.reference_install import install_reference_artifact


TOOL_VERSIONS = {
    "bcftools": "1.24",
    "bgzip": "1.24",
    "exomiser-cli": "15.1.0",
    "java": "21.0.12",
    "python": "3.11.16",
    "tabix": "1.24",
    "vep": "116.1",
}


class EnvironmentHealthTests(unittest.TestCase):
    def test_freezes_and_reverifies_content_free_environment_health(self) -> None:
        with self._prepared_environment() as prepared:
            public, private = prepared
            probe = lambda _root: SystemState(
                architecture="arm64",
                encrypted_mount=True,
                free_bytes=200_000_000_000,
                memory_bytes=8_000_000_000,
                network_blocked=True,
                download_transport_closed=True,
                proxy_environment_clear=True,
            )

            first = verify_environment(public, private, system_probe=probe)
            second = verify_environment(public, private, system_probe=probe)
            receipt = (
                private
                / "health"
                / "2026-08-26.2"
                / "environment-v1.json"
            ).read_text(encoding="utf-8")

        self.assertEqual(first.state, "ready")
        self.assertEqual(second, first)
        self.assertEqual(first.artifact_count, 4)
        self.assertEqual(first.installed_count, 4)
        self.assertEqual(first.tool_count, 7)
        self.assertEqual(first.support_count, 2)
        self.assertEqual(first.check_count, 10)
        self.assertNotIn(str(public), receipt)
        self.assertNotIn(str(private), receipt)

    def test_rejects_a_tool_changed_after_the_receipt_was_written(self) -> None:
        with self._prepared_environment() as prepared:
            public, private = prepared
            verify_environment(public, private, system_probe=self._ready_probe())
            relative = TOOL_PATHS["python"].format(bundle="2026-08-26.2")
            tool = private / relative
            original = tool.read_bytes()
            tool.chmod(0o700)
            tool.write_bytes(b"x" * len(original))
            tool.chmod(0o500)

            with self.assertRaisesRegex(ValueError, "stale_toolchain"):
                verify_environment(public, private, system_probe=self._ready_probe())

    def test_rejects_a_writable_tool_entrypoint(self) -> None:
        with self._prepared_environment() as prepared:
            public, private = prepared
            relative = TOOL_PATHS["python"].format(bundle="2026-08-26.2")
            (private / relative).chmod(0o700)

            with self.assertRaisesRegex(ValueError, "stale_toolchain"):
                verify_environment(public, private, system_probe=self._ready_probe())

    def test_rejects_a_support_tree_changed_after_the_receipt_was_written(self) -> None:
        with self._prepared_environment() as prepared:
            public, private = prepared
            verify_environment(public, private, system_probe=self._ready_probe())
            relative = SUPPORT_PATHS["perl5-runtime"].format(bundle="2026-08-26.2")
            support_file = private / relative / "lib" / "support.dat"
            original = support_file.read_bytes()
            support_file.chmod(0o600)
            support_file.write_bytes(b"x" * len(original))
            support_file.chmod(0o400)

            with self.assertRaisesRegex(ValueError, "stale_toolchain"):
                verify_environment(public, private, system_probe=self._ready_probe())

    def test_rejects_a_symlink_inside_a_support_tree(self) -> None:
        with self._prepared_environment() as prepared:
            public, private = prepared
            relative = SUPPORT_PATHS["vep-htslib"].format(bundle="2026-08-26.2")
            support = private / relative
            support.chmod(0o700)
            os.symlink("lib/support.dat", support / "alias")
            support.chmod(0o500)

            with self.assertRaisesRegex(ValueError, "stale_toolchain"):
                verify_environment(public, private, system_probe=self._ready_probe())

    def test_rejects_an_installed_reference_changed_without_changing_its_size(self) -> None:
        with self._prepared_environment() as prepared:
            public, private = prepared
            verify_environment(public, private, system_probe=self._ready_probe())
            installed = (
                private
                / "references"
                / "2026-08-26.2"
                / "installed"
                / "reference-index"
                / "reference.vcf.gz.tbi"
            )
            original = installed.read_bytes()
            installed.chmod(0o600)
            installed.write_bytes(b"x" * len(original))
            installed.chmod(0o400)

            with self.assertRaisesRegex(ValueError, "stale_environment_receipt"):
                verify_environment(public, private, system_probe=self._ready_probe())

    def test_rejects_an_unresolved_bundle(self) -> None:
        with self._prepared_environment() as prepared:
            public, private = prepared
            manifest_path = public / "config" / "reference-bundle.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["status"] = "declared"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unresolved_reference_digest"):
                verify_environment(public, private, system_probe=self._ready_probe())

    def test_rejects_each_unsafe_system_state(self) -> None:
        base = SystemState(
            architecture="arm64",
            encrypted_mount=True,
            free_bytes=200_000_000_000,
            memory_bytes=8_000_000_000,
            network_blocked=True,
            download_transport_closed=True,
            proxy_environment_clear=True,
        )
        unsafe = {
            "architecture": replace(base, architecture="x86_64"),
            "encryption": replace(base, encrypted_mount=False),
            "free_space": replace(base, free_bytes=99_999_999_999),
            "memory": replace(base, memory_bytes=7_499_999_999),
            "network": replace(base, network_blocked=False),
            "download_transport": replace(base, download_transport_closed=False),
            "proxy": replace(base, proxy_environment_clear=False),
        }
        with self._prepared_environment() as prepared:
            public, private = prepared
            for name, state in unsafe.items():
                with self.subTest(name=name):
                    with self.assertRaisesRegex(ValueError, "environment_not_ready"):
                        verify_environment(
                            public,
                            private,
                            system_probe=lambda _root, value=state: value,
                        )

    def test_rejects_unknown_and_duplicate_toolchain_receipt_fields(self) -> None:
        for mutation in ("unknown", "duplicate"):
            with self.subTest(mutation=mutation), self._prepared_environment() as prepared:
                public, private = prepared
                receipt = (
                    private
                    / "toolchain"
                    / "2026-08-26.2"
                    / "toolchain-receipt.json"
                )
                receipt.chmod(0o600)
                if mutation == "unknown":
                    payload = json.loads(receipt.read_text(encoding="utf-8"))
                    payload["unknown"] = True
                    content = json.dumps(
                        payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ) + "\n"
                else:
                    content = receipt.read_text(encoding="utf-8").replace(
                        '{"architecture":"arm64",',
                        '{"architecture":"arm64","architecture":"arm64",',
                        1,
                    )
                receipt.write_text(content, encoding="utf-8")
                receipt.chmod(0o400)

                with self.assertRaisesRegex(ValueError, "stale_toolchain"):
                    verify_environment(public, private, system_probe=self._ready_probe())

    def test_rejects_a_symlink_inside_an_installed_artifact(self) -> None:
        with self._prepared_environment() as prepared:
            public, private = prepared
            target = (
                private
                / "references"
                / "2026-08-26.2"
                / "installed"
                / "reference-index"
            )
            target.chmod(0o700)
            os.symlink("reference.vcf.gz.tbi", target / "alias")
            target.chmod(0o500)

            with self.assertRaisesRegex(ValueError, "stale_reference_installation"):
                verify_environment(public, private, system_probe=self._ready_probe())

    def test_rejects_a_changed_immutable_health_receipt(self) -> None:
        with self._prepared_environment() as prepared:
            public, private = prepared
            verify_environment(public, private, system_probe=self._ready_probe())
            receipt = (
                private
                / "health"
                / "2026-08-26.2"
                / "environment-v1.json"
            )
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            payload["check_count"] = payload["check_count"] + 1
            receipt.chmod(0o600)
            receipt.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            receipt.chmod(0o400)

            with self.assertRaisesRegex(ValueError, "stale_environment_receipt"):
                verify_environment(public, private, system_probe=self._ready_probe())

    def _prepared_environment(self) -> "_PreparedEnvironment":
        return _PreparedEnvironment()

    @staticmethod
    def _ready_probe():
        return lambda _root: SystemState(
            architecture="arm64",
            encrypted_mount=True,
            free_bytes=200_000_000_000,
            memory_bytes=8_000_000_000,
            network_blocked=True,
            download_transport_closed=True,
            proxy_environment_clear=True,
        )


class _PreparedEnvironment:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()

    def __enter__(self) -> tuple[Path, Path]:
        root = Path(self.temporary.name).resolve()
        public = root / "public"
        private = root / "private"
        config = public / "config"
        config.mkdir(parents=True, mode=0o700)
        private.mkdir(mode=0o700)

        reference_content = b"synthetic-reference-bytes\n"
        tool_payloads = {
            name: f"synthetic-{name}-{version}\n".encode("utf-8")
            for name, version in TOOL_VERSIONS.items()
        }
        archives = {
            "openjdk-macos-aarch64": self._tar_archive(
                "jdk-21.0.12.1+1/Contents/Home/bin/java",
                tool_payloads["java"],
                executable=True,
            ),
            "exomiser-cli": self._tar_archive(
                "exomiser-cli-15.1.0/exomiser-cli-15.1.0.jar",
                tool_payloads["exomiser-cli"],
                executable=False,
            ),
            "ensembl-vep-source": self._tar_archive(
                "ensembl-vep-97c24b205f4ba8b44ccc75b839512a1d59104019/vep",
                tool_payloads["vep"],
                executable=True,
            ),
        }
        source_assets = {
            "reference-index": (
                "reference.vcf.gz.tbi",
                "tabix-index",
                "index",
                reference_content,
            ),
            "openjdk-macos-aarch64": (
                "openjdk-synthetic.tar.gz",
                "source-tar",
                "runtime_archive",
                archives["openjdk-macos-aarch64"],
            ),
            "exomiser-cli": (
                "exomiser-synthetic.tar.gz",
                "source-tar",
                "runtime_archive",
                archives["exomiser-cli"],
            ),
            "ensembl-vep-source": (
                "vep-synthetic.tar.gz",
                "source-tar",
                "tool_source",
                archives["ensembl-vep-source"],
            ),
        }
        artifacts = []
        for name, (filename, install_kind, role, content) in source_assets.items():
            digest = hashlib.sha256(content).hexdigest()
            artifacts.append(
                {
                    "expected_bytes": len(content),
                    "expected_sha256": digest,
                    "filename": filename,
                    "install_kind": install_kind,
                    "name": name,
                    "role": role,
                    "source_checksum": {"algorithm": "sha256", "value": digest},
                    "source_url": f"https://github.com/example/project/releases/download/1.0/{filename}",
                    "version": "1.0",
                }
            )
        manifest = {
            "artifacts": artifacts,
            "assembly": "GRCh38",
            "bundle_version": "2026-08-26.2",
            "fastq_included": False,
            "network_during_private_run": False,
            "private_runtime": "m1-encrypted-workspace",
            "protected_data_allowed_on_public_compute": False,
            "schema_version": 2,
            "status": "verified",
        }
        manifest_path = config / "reference-bundle.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        bundle = load_reference_bundle(manifest_path)
        verified = (
            private
            / "references"
            / bundle.bundle_version
            / "downloads"
            / "verified"
        )
        verified.mkdir(parents=True, mode=0o700)
        for artifact in bundle.artifacts:
            source = verified / artifact.filename
            source.write_bytes(source_assets[artifact.name][3])
            source.chmod(0o400)
            install_reference_artifact(private, bundle, artifact.name)

        tools = []
        for name, version in sorted(TOOL_VERSIONS.items()):
            relative = TOOL_PATHS[name].format(bundle=bundle.bundle_version)
            path = private / relative
            payload = tool_payloads[name]
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                path.write_bytes(payload)
                path.chmod(0o500)
            tools.append(
                {
                    "byte_count": len(payload),
                    "name": name,
                    "relative_path": relative,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "version": version,
                }
            )
        support_payloads = {
            "perl5-runtime": b"synthetic-perl-support\n",
            "vep-htslib": b"synthetic-htslib-support\n",
        }
        supports = []
        for name, version in sorted(SUPPORT_VERSIONS.items()):
            relative = SUPPORT_PATHS[name].format(bundle=bundle.bundle_version)
            root_path = private / relative
            support_file = root_path / "lib" / "support.dat"
            support_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            support_file.write_bytes(support_payloads[name])
            support_file.chmod(0o400)
            support_file.parent.chmod(0o500)
            root_path.chmod(0o500)
            supports.append(self._support_entry(name, version, relative, root_path))
        toolchain_receipt = {
            "architecture": "arm64",
            "bundle_version": bundle.bundle_version,
            "schema_version": 2,
            "supports": supports,
            "tools": tools,
        }
        receipt_path = (
            private
            / "toolchain"
            / bundle.bundle_version
            / "toolchain-receipt.json"
        )
        receipt_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        receipt_path.write_text(
            json.dumps(toolchain_receipt, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        receipt_path.chmod(0o400)
        return public, private

    @staticmethod
    def _support_entry(name: str, version: str, relative: str, root: Path) -> dict[str, object]:
        tree = hashlib.sha256()
        file_count = 0
        directory_count = 0
        byte_count = 0
        for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
            directory_names.sort()
            file_names.sort()
            current_path = Path(current)
            if current_path != root:
                local = current_path.relative_to(root).as_posix().encode("utf-8")
                tree.update(b"D")
                tree.update(len(local).to_bytes(4, "big"))
                tree.update(local)
                directory_count += 1
            for filename in file_names:
                child = current_path / filename
                content = child.read_bytes()
                local = child.relative_to(root).as_posix().encode("utf-8")
                tree.update(b"F")
                tree.update(len(local).to_bytes(4, "big"))
                tree.update(local)
                tree.update(b"x" if child.stat().st_mode & 0o111 else b"-")
                tree.update(len(content).to_bytes(8, "big"))
                tree.update(hashlib.sha256(content).digest())
                file_count += 1
                byte_count += len(content)
        return {
            "byte_count": byte_count,
            "directory_count": directory_count,
            "file_count": file_count,
            "name": name,
            "relative_path": relative,
            "tree_sha256": tree.hexdigest(),
            "version": version,
        }

    @staticmethod
    def _tar_archive(name: str, content: bytes, *, executable: bool) -> bytes:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            member.mode = 0o755 if executable else 0o644
            archive.addfile(member, io.BytesIO(content))
        return stream.getvalue()

    def __exit__(self, *_args: object) -> None:
        self.temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
