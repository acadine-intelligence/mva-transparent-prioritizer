from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mva_prioritizer.safe_projection import project_safe_learning


class SafeProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.private = self.base / "controlled"
        self.public = self.base / "public"
        self.private.mkdir(mode=0o700)
        self.public.mkdir(mode=0o755)
        source_dir = self.private / "run"
        source_dir.mkdir(mode=0o700)
        self.source = source_dir / "safe-learnings.json"
        self.safe_learning = {
            "external_actions": 0,
            "finding_count": 2,
            "finding_type_counts": {"pair": 1, "single": 1},
            "method_version": "transparent-review-v1",
            "schema_version": 1,
            "state": "review_ready",
            "synthetic": True,
            "warning_count": 1,
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_projects_only_the_fixed_safe_schema_to_a_derived_filename(self) -> None:
        self._write_source(self.safe_learning)

        result = project_safe_learning(
            private_root=self.private,
            source_relative_path="run/safe-learnings.json",
            public_output_root=self.public,
            forbidden_values=(b"SYNTHETIC_PROTECTED_CANARY",),
        )

        self.assertEqual(result.state, "projected")
        self.assertEqual(result.external_actions, 0)
        self.assertEqual(result.output_name, "safe-learnings.json")
        output = self.public / result.output_name
        self.assertTrue(output.is_file())
        self.assertEqual(json.loads(output.read_bytes()), self.safe_learning)

    def test_rejects_an_unknown_field_without_writing_or_reflecting_it(self) -> None:
        unsafe = dict(self.safe_learning)
        unsafe["candidate_id"] = "SYNTHETIC_PROTECTED_CANARY"
        self._write_source(unsafe)

        with self.assertRaises(ValueError) as captured:
            project_safe_learning(
                private_root=self.private,
                source_relative_path="run/safe-learnings.json",
                public_output_root=self.public,
                forbidden_values=(b"SYNTHETIC_PROTECTED_CANARY",),
            )

        self.assertEqual(str(captured.exception), "invalid_safe_learning")
        self.assertFalse((self.public / "safe-learnings.json").exists())
        self.assertNotIn("CANARY", str(captured.exception))

    def test_blocks_a_forbidden_value_inside_an_allowlisted_field(self) -> None:
        unsafe = dict(self.safe_learning)
        unsafe["method_version"] = "synthetic-protected-canary"
        self._write_source(unsafe)

        with self.assertRaises(ValueError) as captured:
            project_safe_learning(
                private_root=self.private,
                source_relative_path="run/safe-learnings.json",
                public_output_root=self.public,
                forbidden_values=(b"synthetic-protected-canary",),
            )

        self.assertEqual(str(captured.exception), "privacy_blocked")
        self.assertFalse((self.public / "safe-learnings.json").exists())

    def test_refuses_to_replace_an_existing_public_projection(self) -> None:
        self._write_source(self.safe_learning)
        existing = self.public / "safe-learnings.json"
        existing.write_bytes(b"reviewer-owned\n")

        with self.assertRaisesRegex(ValueError, "output_exists"):
            project_safe_learning(
                private_root=self.private,
                source_relative_path="run/safe-learnings.json",
                public_output_root=self.public,
                forbidden_values=(b"SYNTHETIC_PROTECTED_CANARY",),
            )

        self.assertEqual(existing.read_bytes(), b"reviewer-owned\n")
        self.assertFalse((self.public / "safe-learnings.json.tmp").exists())

    def test_rejects_a_caller_selected_output_inside_the_private_root(self) -> None:
        self._write_source(self.safe_learning)

        with self.assertRaisesRegex(ValueError, "root_overlap"):
            project_safe_learning(
                private_root=self.private,
                source_relative_path="run/safe-learnings.json",
                public_output_root=self.private,
                forbidden_values=(b"SYNTHETIC_PROTECTED_CANARY",),
            )

        self.assertFalse((self.private / "safe-learnings.json").exists())

    def _write_source(self, value: dict[str, object]) -> None:
        self.source.write_text(
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.source.chmod(0o400)


if __name__ == "__main__":
    unittest.main()
