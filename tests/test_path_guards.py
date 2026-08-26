from __future__ import annotations

import os
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mva_prioritizer.paths import (
    PathSecurityError,
    hash_regular_input,
    read_regular_input,
    validate_root_pair,
)


class PathGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.public = self.base / "public"
        self.private = self.base / "controlled"
        self.public.mkdir(mode=0o755)
        self.private.mkdir(mode=0o700)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_reads_only_a_regular_file_below_a_disjoint_private_root(self) -> None:
        data = self.private / "data"
        data.mkdir(mode=0o700)
        input_file = data / "input.bin"
        input_file.write_bytes(b"synthetic-bytes")
        input_file.chmod(0o400)

        roots = validate_root_pair(self.public, self.private)

        self.assertEqual(read_regular_input(roots.private_root, "data/input.bin", max_bytes=32), b"synthetic-bytes")
        self.assertEqual(roots.public_root, self.public.resolve())
        self.assertEqual(roots.private_root, self.private.resolve())

    def test_hashes_a_regular_file_without_loading_it_as_one_buffer(self) -> None:
        data = self.private / "data"
        data.mkdir(mode=0o700)
        content = (b"synthetic-reference-block\n" * 50_000) + b"end\n"
        input_file = data / "reference.bin"
        input_file.write_bytes(content)
        input_file.chmod(0o400)

        result = hash_regular_input(
            self.private,
            "data/reference.bin",
            max_bytes=len(content),
            chunk_bytes=4096,
        )

        self.assertEqual(result.byte_count, len(content))
        self.assertEqual(result.sha256, hashlib.sha256(content).hexdigest())

    def test_rejects_equal_nested_and_ancestor_roots(self) -> None:
        with self.assertRaisesRegex(PathSecurityError, "root_overlap"):
            validate_root_pair(self.public, self.public)

        nested = self.public / "controlled"
        nested.mkdir(mode=0o700)
        with self.assertRaisesRegex(PathSecurityError, "root_overlap"):
            validate_root_pair(self.public, nested)

        private_ancestor = self.base / "private-ancestor"
        private_ancestor.mkdir(mode=0o700)
        public_child = private_ancestor / "repo"
        public_child.mkdir(mode=0o755)
        with self.assertRaisesRegex(PathSecurityError, "root_overlap"):
            validate_root_pair(public_child, private_ancestor)

    def test_rejects_symlink_root_symlink_input_directory_fifo_and_oversize(self) -> None:
        data = self.private / "data"
        data.mkdir(mode=0o700)
        regular = data / "regular.bin"
        regular.write_bytes(b"0123456789")
        regular.chmod(0o400)
        symlink = data / "link.bin"
        symlink.symlink_to(regular)
        fifo = data / "pipe"
        os.mkfifo(fifo, 0o600)

        private_link = self.base / "controlled-link"
        private_link.symlink_to(self.private, target_is_directory=True)
        with self.assertRaisesRegex(PathSecurityError, "symlink_component"):
            validate_root_pair(self.public, private_link)

        roots = validate_root_pair(self.public, self.private)
        with self.assertRaisesRegex(PathSecurityError, "symlink_component"):
            read_regular_input(roots.private_root, "data/link.bin", max_bytes=32)
        with self.assertRaisesRegex(PathSecurityError, "not_regular"):
            read_regular_input(roots.private_root, "data", max_bytes=32)
        with self.assertRaisesRegex(PathSecurityError, "not_regular"):
            read_regular_input(roots.private_root, "data/pipe", max_bytes=32)
        with self.assertRaisesRegex(PathSecurityError, "size_limit"):
            read_regular_input(roots.private_root, "data/regular.bin", max_bytes=3)

    def test_rejects_unsafe_relative_names_before_open(self) -> None:
        roots = validate_root_pair(self.public, self.private)
        for relative in (
            "",
            ".",
            "..",
            "../escape",
            "data/../../escape",
            "/absolute",
            "data//input.bin",
            "data/./input.bin",
            "data/bad\nname",
            "data\\input.bin",
        ):
            with self.subTest(relative=relative):
                with self.assertRaisesRegex(PathSecurityError, "invalid_relative_path"):
                    read_regular_input(roots.private_root, relative, max_bytes=32)


if __name__ == "__main__":
    unittest.main()
