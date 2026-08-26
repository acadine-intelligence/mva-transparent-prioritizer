from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mva_prioritizer.privacy_scan import scan_public_tree


class PrivacyScanTests(unittest.TestCase):
    def test_reports_only_counts_for_a_clean_public_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            public = Path(temporary).resolve() / "public"
            nested = public / "nested"
            nested.mkdir(parents=True, mode=0o700)
            first = public / "safe.json"
            second = nested / "method.txt"
            first.write_bytes(b'{"state":"projected"}\n')
            second.write_bytes(b"synthetic aggregate only\n")
            expected_bytes = first.stat().st_size + second.stat().st_size

            result = scan_public_tree(
                public_root=public,
                forbidden_values=(b"synthetic-protected-canary",),
            )

        self.assertEqual(result.state, "clear")
        self.assertEqual(result.file_count, 2)
        self.assertEqual(result.byte_count, expected_bytes)
        self.assertEqual(result.external_actions, 0)

    def test_blocks_a_canary_without_reporting_its_value_or_location(self) -> None:
        canary = b"synthetic-protected-canary-1147"
        with tempfile.TemporaryDirectory() as temporary:
            public = Path(temporary).resolve() / "public"
            public.mkdir(mode=0o700)
            (public / "candidate.json").write_bytes(b'{"value":"' + canary + b'"}\n')

            with self.assertRaises(ValueError) as captured:
                scan_public_tree(public_root=public, forbidden_values=(canary,))

        self.assertEqual(str(captured.exception), "privacy_blocked")
        self.assertNotIn(canary.decode("utf-8"), str(captured.exception))

    def test_rejects_a_symlink_in_the_public_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            public = root / "public"
            public.mkdir(mode=0o700)
            outside = root / "outside.txt"
            outside.write_bytes(b"synthetic-protected-canary")
            (public / "linked.txt").symlink_to(outside)

            with self.assertRaises(ValueError) as captured:
                scan_public_tree(
                    public_root=public,
                    forbidden_values=(b"synthetic-protected-canary",),
                )

        self.assertEqual(str(captured.exception), "unsafe_public_tree")


if __name__ == "__main__":
    unittest.main()
