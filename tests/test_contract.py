from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mva_prioritizer.contract import load_contract


class ContractTests(unittest.TestCase):
    def test_loads_one_versioned_contract_for_every_public_harness_boundary(self) -> None:
        contract = load_contract()

        self.assertEqual(contract.value["schema_version"], 1)
        self.assertEqual(contract.value["method_version"], "transparent-review-v1")
        self.assertEqual(
            set(contract.value),
            {
                "dossier",
                "manifest",
                "method_version",
                "privacy_scan",
                "public_source_scan",
                "run_artifacts",
                "run_receipt",
                "safe_learning",
                "schema_version",
                "scoring_config",
                "synthetic_fixture",
            },
        )
        self.assertRegex(contract.sha256, r"^[0-9a-f]{64}$")
        self.assertEqual(
            contract.value["run_artifacts"],
            [
                "dossier.json",
                "dossier.md",
                "receipt.json",
                "run.json",
                "safe-learnings.json",
            ],
        )
        self.assertEqual(
            contract.value["safe_learning"]["output_name"],
            "safe-learnings.json",
        )
        self.assertIn(".vcf.gz", contract.value["public_source_scan"]["denied_suffixes"])
        self.assertIn(".env", contract.value["public_source_scan"]["denied_names"])


if __name__ == "__main__":
    unittest.main()
