from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mva_prioritizer.source_scan import scan_public_source_tree


class PublicSourceScanTests(unittest.TestCase):
    def _repository(self, temporary: str) -> Path:
        root = Path(temporary).resolve() / "public"
        root.mkdir(mode=0o700)
        completed = subprocess.run(
            ["git", "init", "-q", "-b", "test"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        (root / ".gitignore").write_text("private/\n__pycache__/\n", encoding="utf-8")
        return root

    def test_scans_only_stageable_public_files_and_reports_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(temporary)
            (root / "README.md").write_text("Synthetic methods only.\n", encoding="utf-8")
            private = root / "private"
            private.mkdir(mode=0o700)
            (private / "ignored.txt").write_bytes(b"sk-" + (b"A" * 24))

            result = scan_public_source_tree(root)

        self.assertEqual(result.state, "clear")
        self.assertEqual(result.file_count, 2)
        self.assertGreater(result.byte_count, 0)
        self.assertEqual(result.external_actions, 0)

    def test_blocks_source_machine_paths_without_reflecting_them(self) -> None:
        source_path = "/" + "Users" + "/example/private/input"
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(temporary)
            (root / "metadata.json").write_text(source_path, encoding="utf-8")

            with self.assertRaises(ValueError) as captured:
                scan_public_source_tree(root)

        self.assertEqual(str(captured.exception), "privacy_blocked")
        self.assertNotIn(source_path, str(captured.exception))

    def test_blocks_genomic_artifacts_and_credential_shapes(self) -> None:
        cases = {
            "genomic_artifact": ("case.vcf.gz", b"synthetic"),
            "credential_shape": ("config.txt", b"sk-" + (b"A" * 24)),
        }
        for label, (name, payload) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = self._repository(temporary)
                (root / name).write_bytes(payload)

                with self.assertRaises(ValueError) as captured:
                    scan_public_source_tree(root)

                self.assertEqual(str(captured.exception), "privacy_blocked")


class PublicSourceScanCommandTests(unittest.TestCase):
    def test_repository_scan_returns_content_free_status(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/verify_public_tree.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertRegex(
            completed.stdout,
            r'^\{"byte_count":[0-9]+,"external_actions":0,"file_count":[0-9]+,"state":"clear"\}\n$',
        )
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
