from __future__ import annotations

import io
import stat
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from mva_prioritizer.reference_bundle import ReferenceArtifact, ReferenceBundle
from mva_prioritizer.reference_install import install_reference_artifact


class ReferenceInstallationTests(unittest.TestCase):
    def test_installs_a_safe_tar_archive_into_the_fixed_private_directory(self) -> None:
        content = b"#!/bin/sh\nprintf 'synthetic tool\\n'\n"
        archive = self._tar_archive("package/tool", content, mode=0o755)

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            result = install_reference_artifact(private, bundle, "tool-source")
            installation_root = (
                private
                / "references"
                / bundle.bundle_version
                / "installed"
                / "tool-source"
            )
            installed = installation_root / "package" / "tool"

            self.assertEqual(installed.read_bytes(), content)
            self.assertTrue(installed.stat().st_mode & stat.S_IXUSR)
            self.assertEqual(stat.S_IMODE(installation_root.stat().st_mode), 0o500)

        self.assertEqual(result.state, "installed")
        self.assertEqual(result.file_count, 1)
        self.assertEqual(result.byte_count, len(content))

    def test_rejects_tar_traversal_before_any_installation_is_published(self) -> None:
        archive = self._tar_archive("../escape.txt", b"escape")

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                install_reference_artifact(private, bundle, "tool-source")

            self.assertFalse((private / "escape.txt").exists())
            self.assertFalse(
                (
                    private
                    / "references"
                    / bundle.bundle_version
                    / "installed"
                    / "tool-source"
                ).exists()
            )

    def test_materializes_a_proven_in_tree_directory_symlink_as_regular_tree(self) -> None:
        archive = self._tar_archive_with_entries(
            [
                ("directory", "package", None),
                ("directory", "package/source", None),
                ("file", "package/source/value.txt", b"safe-source"),
                ("symlink", "package/view", "source/"),
            ]
        )

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            result = install_reference_artifact(private, bundle, "tool-source")
            installed = (
                private
                / "references"
                / bundle.bundle_version
                / "installed"
                / "tool-source"
                / "package"
                / "view"
            )

            self.assertTrue(installed.is_dir())
            self.assertFalse(installed.is_symlink())
            self.assertEqual((installed / "value.txt").read_bytes(), b"safe-source")
            self.assertFalse((installed / "value.txt").is_symlink())
            self.assertEqual(result.file_count, 2)

    def test_materializes_an_in_tree_target_reached_through_another_symlink(self) -> None:
        archive = self._tar_archive_with_entries(
            [
                ("directory", "package", None),
                ("directory", "package/modules", None),
                ("directory", "package/modules/sub", None),
                ("file", "package/modules/sub/value.txt", b"nested-source"),
                ("directory", "package/src", None),
                ("directory", "package/src/perl", None),
                ("symlink", "package/src/perl/modules", "../../modules"),
                ("symlink", "package/src/perl/view", "modules/sub"),
            ]
        )

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            install_reference_artifact(private, bundle, "tool-source")
            installed = (
                private
                / "references"
                / bundle.bundle_version
                / "installed"
                / "tool-source"
                / "package"
                / "src"
                / "perl"
            )

            self.assertFalse((installed / "modules").is_symlink())
            self.assertFalse((installed / "view").is_symlink())
            self.assertEqual((installed / "view" / "value.txt").read_bytes(), b"nested-source")

    def test_materializes_a_proven_in_tree_file_symlink_as_a_regular_file(self) -> None:
        archive = self._tar_archive_with_entries(
            [
                ("directory", "package", None),
                ("file", "package/source.txt", b"safe-file"),
                ("symlink", "package/view.txt", "source.txt"),
            ]
        )

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            install_reference_artifact(private, bundle, "tool-source")
            installed = (
                private
                / "references"
                / bundle.bundle_version
                / "installed"
                / "tool-source"
                / "package"
                / "view.txt"
            )

            self.assertTrue(installed.is_file())
            self.assertFalse(installed.is_symlink())
            self.assertEqual(installed.read_bytes(), b"safe-file")

    def test_rejects_tar_link_that_escapes_the_archive_root(self) -> None:
        archive = self._tar_archive_with_entries(
            [("symlink", "package/link", "../../escape")]
        )

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                install_reference_artifact(private, bundle, "tool-source")

    def test_rejects_absolute_tar_link(self) -> None:
        archive = self._tar_archive_with_entries(
            [("symlink", "package/link", "/etc/passwd")]
        )

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                install_reference_artifact(private, bundle, "tool-source")

    def test_rejects_broken_tar_link(self) -> None:
        archive = self._tar_archive_with_entries(
            [("symlink", "package/link", "missing")]
        )

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                install_reference_artifact(private, bundle, "tool-source")

    def test_rejects_cyclic_tar_links(self) -> None:
        archive = self._tar_archive_with_entries(
            [
                ("directory", "package", None),
                ("symlink", "package/a", "b"),
                ("symlink", "package/b", "a"),
            ]
        )

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                install_reference_artifact(private, bundle, "tool-source")

    def test_rejects_special_tar_member(self) -> None:
        archive = self._tar_archive_with_entries(
            [
                ("directory", "package", None),
                ("fifo", "package/pipe", None),
            ]
        )

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                install_reference_artifact(private, bundle, "tool-source")

    def test_rejects_ambiguous_link_namespace(self) -> None:
        archive = self._tar_archive_with_entries(
            [
                ("directory", "package", None),
                ("directory", "package/source", None),
                ("file", "package/source/value.txt", b"source"),
                ("symlink", "package/view", "source"),
                ("file", "package/view/injected.txt", b"ambiguous"),
            ]
        )

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                install_reference_artifact(private, bundle, "tool-source")

    def test_rejects_ambiguous_link_target_syntax(self) -> None:
        for link_target in ("source//value.txt", "./source", "source/."):
            with self.subTest(link_target=link_target):
                archive = self._tar_archive_with_entries(
                    [
                        ("directory", "package", None),
                        ("directory", "package/source", None),
                        ("file", "package/source/value.txt", b"source"),
                        ("symlink", "package/view", link_target),
                    ]
                )

                with self._prepared_asset(
                    archive,
                    "tool-1.0.tar.gz",
                    "source-tar",
                ) as prepared:
                    private, bundle = prepared
                    with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                        install_reference_artifact(private, bundle, "tool-source")

    def test_rejects_ambiguous_link_path_syntax(self) -> None:
        archive = self._tar_archive_with_entries(
            [
                ("directory", "package", None),
                ("directory", "package/source", None),
                ("file", "package/source/value.txt", b"source"),
                ("symlink", "package/./view", "source"),
            ]
        )

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                install_reference_artifact(private, bundle, "tool-source")

    def test_rejects_a_directory_form_link_to_a_file(self) -> None:
        archive = self._tar_archive_with_entries(
            [
                ("directory", "package", None),
                ("file", "package/source.txt", b"source"),
                ("symlink", "package/view", "source.txt/"),
            ]
        )

        with self._prepared_asset(archive, "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                install_reference_artifact(private, bundle, "tool-source")

    def test_rejects_tar_hard_link(self) -> None:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            source = tarfile.TarInfo("package/source.txt")
            source.size = 4
            archive.addfile(source, io.BytesIO(b"safe"))
            link = tarfile.TarInfo("package/view.txt")
            link.type = tarfile.LNKTYPE
            link.linkname = "package/source.txt"
            archive.addfile(link)

        with self._prepared_asset(stream.getvalue(), "tool-1.0.tar.gz", "source-tar") as prepared:
            private, bundle = prepared
            with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                install_reference_artifact(private, bundle, "tool-source")

    def test_installs_a_safe_zip_and_rejects_zip_symlinks(self) -> None:
        safe_stream = io.BytesIO()
        with zipfile.ZipFile(safe_stream, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("package/data.txt", b"safe-data")

        with self._prepared_asset(safe_stream.getvalue(), "tool-1.0.zip", "archive") as prepared:
            private, bundle = prepared
            result = install_reference_artifact(private, bundle, "tool-source")
            installed = (
                private
                / "references"
                / bundle.bundle_version
                / "installed"
                / "tool-source"
                / "package"
                / "data.txt"
            )
            self.assertEqual(installed.read_bytes(), b"safe-data")
            self.assertEqual(result.file_count, 1)

        unsafe_stream = io.BytesIO()
        with zipfile.ZipFile(unsafe_stream, mode="w") as archive:
            link = zipfile.ZipInfo("package/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "../../escape")

        with self._prepared_asset(unsafe_stream.getvalue(), "tool-1.0.zip", "archive") as prepared:
            private, bundle = prepared
            with self.assertRaisesRegex(ValueError, "unsafe_archive_member"):
                install_reference_artifact(private, bundle, "tool-source")

    def test_installs_a_plain_verified_reference_without_overwriting_it(self) -> None:
        content = b"synthetic-index-bytes"
        with self._prepared_asset(content, "reference.vcf.gz.tbi", "tabix-index") as prepared:
            private, bundle = prepared
            first = install_reference_artifact(private, bundle, "tool-source")
            installed = (
                private
                / "references"
                / bundle.bundle_version
                / "installed"
                / "tool-source"
                / "reference.vcf.gz.tbi"
            )
            self.assertEqual(installed.read_bytes(), content)
            self.assertEqual(first.file_count, 1)

            with self.assertRaisesRegex(ValueError, "existing_reference_installation"):
                install_reference_artifact(private, bundle, "tool-source")

    def test_rejects_installation_from_an_unresolved_digest(self) -> None:
        content = b"synthetic-index-bytes"
        with self._prepared_asset(content, "reference.vcf.gz.tbi", "tabix-index") as prepared:
            private, bundle = prepared
            unresolved = ReferenceBundle(
                bundle_version=bundle.bundle_version,
                assembly=bundle.assembly,
                status="declared",
                artifacts=(
                    ReferenceArtifact(
                        name=bundle.artifacts[0].name,
                        role=bundle.artifacts[0].role,
                        version=bundle.artifacts[0].version,
                        source_url=bundle.artifacts[0].source_url,
                        filename=bundle.artifacts[0].filename,
                        expected_bytes=bundle.artifacts[0].expected_bytes,
                        expected_sha256=None,
                        source_checksum_algorithm="none",
                        source_checksum_value=None,
                        install_kind=bundle.artifacts[0].install_kind,
                    ),
                ),
            )

            with self.assertRaisesRegex(ValueError, "unresolved_reference_digest"):
                install_reference_artifact(private, unresolved, "tool-source")

    def _prepared_asset(
        self,
        content: bytes,
        filename: str,
        install_kind: str,
    ) -> "_PreparedAsset":
        return _PreparedAsset(content, filename, install_kind)

    def _tar_archive(self, name: str, content: bytes, *, mode: int = 0o644) -> bytes:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            member.mode = mode
            archive.addfile(member, io.BytesIO(content))
        return stream.getvalue()

    def _tar_archive_with_entries(
        self,
        entries: list[tuple[str, str, bytes | str | None]],
    ) -> bytes:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            for kind, name, value in entries:
                member = tarfile.TarInfo(name)
                if kind == "directory":
                    if value is not None:
                        raise AssertionError("directory_fixture_value")
                    member.type = tarfile.DIRTYPE
                    member.mode = 0o755
                    archive.addfile(member)
                elif kind == "file":
                    if not isinstance(value, bytes):
                        raise AssertionError("file_fixture_value")
                    member.size = len(value)
                    archive.addfile(member, io.BytesIO(value))
                elif kind == "symlink":
                    if not isinstance(value, str):
                        raise AssertionError("link_fixture_value")
                    member.type = tarfile.SYMTYPE
                    member.linkname = value
                    archive.addfile(member)
                elif kind == "fifo":
                    if value is not None:
                        raise AssertionError("fifo_fixture_value")
                    member.type = tarfile.FIFOTYPE
                    archive.addfile(member)
                else:
                    raise AssertionError("unknown_fixture_kind")
        return stream.getvalue()


class _PreparedAsset:
    def __init__(self, content: bytes, filename: str, install_kind: str) -> None:
        self.content = content
        self.filename = filename
        self.install_kind = install_kind
        self.temporary = tempfile.TemporaryDirectory()

    def __enter__(self) -> tuple[Path, ReferenceBundle]:
        import hashlib

        private = Path(self.temporary.name).resolve() / "private"
        private.mkdir(mode=0o700)
        digest = hashlib.sha256(self.content).hexdigest()
        artifact = ReferenceArtifact(
            name="tool-source",
            role="tool_source",
            version="1.0",
            source_url=f"https://github.com/example/project/releases/download/1.0/{self.filename}",
            filename=self.filename,
            expected_bytes=len(self.content),
            expected_sha256=digest,
            source_checksum_algorithm="sha256",
            source_checksum_value=digest,
            install_kind=self.install_kind,
        )
        bundle = ReferenceBundle(
            bundle_version="2026-08-26.2",
            assembly="GRCh38",
            status="verified",
            artifacts=(artifact,),
        )
        verified = (
            private
            / "references"
            / bundle.bundle_version
            / "downloads"
            / "verified"
        )
        verified.mkdir(parents=True, mode=0o700)
        source = verified / self.filename
        source.write_bytes(self.content)
        source.chmod(0o400)
        return private, bundle

    def __exit__(self, *_args: object) -> None:
        self.temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
