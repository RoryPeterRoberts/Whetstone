import json
import pathlib
import tempfile
import unittest
from unittest import mock

import teach
import teacher
import validation


ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "validated-finding.json"


class TestValidatedExample(unittest.TestCase):
    def test_checked_in_example_is_confirmed_by_current_repository_files(self):
        finding = json.loads(EXAMPLE.read_text())
        repository = finding["evidence_chain"]["repository"]
        verified, rejected = validation.verify_repository_evidence(
            ROOT, repository["evidence"]
        )
        self.assertEqual(rejected, [])
        self.assertEqual(len(verified), 2)
        self.assertEqual(finding["classification"], "confirmed")
        self.assertEqual(finding["evidence_rank"], validation.evidence_tier(finding))
        self.assertEqual(
            [item["file_sha256"] for item in verified],
            [item["file_sha256"] for item in repository["evidence"]],
        )


class TestTeachingUsesValidation(unittest.TestCase):
    def finding(self):
        return {
            "project": "project",
            "pattern": "pattern",
            "current_move": "move",
            "why": "reason",
            "classification": "confirmed",
            "validation_reason": "current code proves it",
            "repository_evidence": [{
                "path": "src/example.py", "line_start": 1, "line_end": 1,
                "excerpt": "old_call()", "supports": "gap", "verified": True,
            }],
            "evidence_chain": {"history": {}, "frontier": {}, "repository": {}},
        }

    def test_lesson_prompt_exposes_repository_verdict_and_exact_evidence(self):
        prompt = teach.gap_prompt(self.finding())
        self.assertIn("Repository validation: confirmed", prompt)
        self.assertIn("current code proves it", prompt)
        self.assertIn("src/example.py:1-1", prompt)
        self.assertIn("old_call()", prompt)

    @mock.patch.object(teacher, "call_codex")
    def test_bank_preserves_full_evidence_chain(self, call_codex):
        call_codex.return_value = "DIRECTION: do it\nPRINCIPLE: verify first\nTELL: tests pass"
        with tempfile.TemporaryDirectory() as td:
            bank = pathlib.Path(td) / "bank.jsonl"
            taught = pathlib.Path(td) / "taught.jsonl"
            with mock.patch.object(teacher, "BANK", bank), mock.patch.object(teach, "TAUGHT", taught):
                teach.teach_gap(self.finding())
            entry = json.loads(bank.read_text().splitlines()[0])
        self.assertEqual(entry["classification"], "confirmed")
        self.assertEqual(entry["validation_reason"], "current code proves it")
        self.assertEqual(entry["evidence_chain"], self.finding()["evidence_chain"])
        self.assertTrue(entry["repository_evidence"][0]["verified"])


if __name__ == "__main__":
    unittest.main()
