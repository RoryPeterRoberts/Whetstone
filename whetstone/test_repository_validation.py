import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import filter as flt
import validation


class RepositoryFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.temp.name)
        (self.repo / "src").mkdir()
        self.code = "alpha = 1\nbeta = 2\ngamma = alpha + beta\n"
        (self.repo / "src" / "example.py").write_text(self.code)

    def tearDown(self):
        self.temp.cleanup()

    def citation(self, **overrides):
        value = {
            "path": "src/example.py",
            "line_start": 1,
            "line_end": 2,
            "excerpt": "alpha = 1\nbeta = 2",
            "supports": "gap",
        }
        value.update(overrides)
        return value


class TestRepositoryEvidence(RepositoryFixture):
    def test_exact_current_code_citation_is_verified_and_hashed(self):
        verified, rejected = validation.verify_repository_evidence(
            self.repo, [self.citation()]
        )
        self.assertEqual(rejected, [])
        self.assertTrue(verified[0]["verified"])
        self.assertEqual(
            verified[0]["file_sha256"], hashlib.sha256(self.code.encode()).hexdigest()
        )

    def test_wrong_excerpt_is_rejected(self):
        verified, rejected = validation.verify_repository_evidence(
            self.repo, [self.citation(excerpt="invented")]
        )
        self.assertEqual(verified, [])
        self.assertIn("does not exactly match", rejected[0]["rejection_reason"])

    def test_absolute_and_traversal_paths_are_rejected(self):
        citations = [
            self.citation(path=str((self.repo / "src/example.py").resolve())),
            self.citation(path="../outside.py"),
        ]
        verified, rejected = validation.verify_repository_evidence(self.repo, citations)
        self.assertEqual(verified, [])
        self.assertEqual(len(rejected), 2)

    def test_overlong_range_is_rejected(self):
        long_file = "\n".join(f"line {i}" for i in range(30)) + "\n"
        (self.repo / "long.txt").write_text(long_file)
        verified, rejected = validation.verify_repository_evidence(self.repo, [{
            "path": "long.txt", "line_start": 1, "line_end": 21,
            "excerpt": "\n".join(long_file.splitlines()[:21]),
        }])
        self.assertEqual(verified, [])
        self.assertIn("overlong", rejected[0]["rejection_reason"])

    def test_symlink_outside_repository_is_rejected(self):
        with tempfile.NamedTemporaryFile("w") as outside:
            outside.write("secret\n"); outside.flush()
            (self.repo / "escape").symlink_to(outside.name)
            verified, rejected = validation.verify_repository_evidence(self.repo, [{
                "path": "escape", "line_start": 1, "line_end": 1, "excerpt": "secret",
            }])
        self.assertEqual(verified, [])
        self.assertIn("inside the repository", rejected[0]["rejection_reason"])


class TestClassification(RepositoryFixture):
    def proposal(self, name="p"):
        return {"pattern": name, "current_move": "m", "why": "w", "evidence": "old"}

    def response(self, classification, citation=True):
        evidence = [self.citation()] if citation else []
        return json.dumps([{
            "proposal_id": "P1", "classification": classification,
            "reason": "checked current code", "repository_evidence": evidence,
        }])

    def test_all_four_classifications_are_preserved(self):
        for classification in validation.CLASSIFICATIONS:
            with self.subTest(classification=classification):
                result = validation.validate(
                    [self.proposal()], self.repo,
                    caller=lambda _repo, _prompt, c=classification: self.response(c),
                )[0]
                self.assertEqual(result["classification"], classification)

    def test_actionable_verdict_without_exact_evidence_is_downgraded(self):
        result = validation.validate(
            [self.proposal()], self.repo,
            caller=lambda _repo, _prompt: self.response("confirmed", citation=False),
        )[0]
        self.assertEqual(result["classification"], "insufficient-evidence")
        self.assertIn("downgraded", result["reason"])

    def test_invalid_evidence_is_retained_as_rejected(self):
        response = json.dumps([{
            "proposal_id": "P1", "classification": "partial", "reason": "maybe",
            "repository_evidence": [self.citation(excerpt="fabricated")],
        }])
        result = validation.validate(
            [self.proposal()], self.repo, caller=lambda _repo, _prompt: response
        )[0]
        self.assertEqual(result["classification"], "insufficient-evidence")
        self.assertEqual(len(result["rejected_repository_evidence"]), 1)

    def test_missing_result_and_validator_failure_fail_closed_for_every_proposal(self):
        proposals = [self.proposal("a"), self.proposal("b")]
        missing = validation.validate(proposals, self.repo, caller=lambda *_: "[]")
        self.assertEqual([r["classification"] for r in missing],
                         ["insufficient-evidence", "insufficient-evidence"])

        def fail(*_args):
            raise RuntimeError("offline")

        failed = validation.validate(proposals, self.repo, caller=fail)
        self.assertEqual(len(failed), 2)
        self.assertTrue(all("validation failed" in r["reason"] for r in failed))

    def test_missing_repository_path_fails_closed(self):
        result = validation.validate([self.proposal()], None)[0]
        self.assertEqual(result["classification"], "insufficient-evidence")
        self.assertIn("path was not provided", result["reason"])


class TestEvidenceRanking(unittest.TestCase):
    def test_doubly_grounded_then_repo_confirmed_then_handled_then_insufficient(self):
        findings = [
            {"classification": "insufficient-evidence", "grounded": True},
            {"classification": "already-handled", "grounded": True},
            {"classification": "confirmed", "grounded": False},
            {"classification": "partial", "grounded": True},
        ]
        self.assertEqual(
            [validation.evidence_tier(f) for f in findings], [3, 2, 1, 0]
        )

    def test_prompt_names_every_classification_and_requires_current_code(self):
        for classification in validation.CLASSIFICATIONS:
            self.assertIn(classification, validation.PROMPT)
        self.assertIn("CURRENT code", validation.PROMPT)
        self.assertIn("exactly equal", validation.PROMPT)


class TestFilterIntegration(unittest.TestCase):
    @mock.patch("canon.canonicalize", return_value={})
    @mock.patch.object(flt, "frontier_index")
    @mock.patch.object(flt, "judge")
    @mock.patch.object(validation, "validate")
    def test_all_findings_are_audited_but_only_actionable_reach_gaps(
            self, validate, judge, frontier_index, _canonicalize):
        with tempfile.TemporaryDirectory() as td:
            repo = pathlib.Path(td) / "project"
            repo.mkdir()
            findings_path = pathlib.Path(td) / "findings.jsonl"
            gaps_path = pathlib.Path(td) / "gaps.jsonl"
            rows = [
                {"repo": "project", "pattern": name, "evidence": f"history-{name}",
                 "commit": f"commit-{name}"}
                for name in ("doubly", "repo-only", "handled", "unknown")
            ]
            judge.return_value = [
                {"pattern": name, "gap": True, "current_move": "m", "why": "w",
                 "confidence": "high", "risk": "quality",
                 "source_ids": ["F1"] if name in ("doubly", "handled") else []}
                for name in ("doubly", "repo-only", "handled", "unknown")
            ]
            frontier_index.return_value = (
                "F1 [source] title", {"F1": {"source": "source", "title": "title", "link": "url"}}
            )
            state = {"path": str(repo), "head": "abc", "dirty": False, "status": []}
            classifications = ("confirmed", "partial", "already-handled", "insufficient-evidence")
            validate.return_value = [{
                "proposal_id": f"P{i}", "classification": classification,
                "reason": f"reason-{classification}", "repository": state,
                "repository_evidence": [], "rejected_repository_evidence": [],
            } for i, classification in enumerate(classifications, 1)]

            with mock.patch.object(flt, "FINDINGS", findings_path), \
                    mock.patch.object(flt, "GAPS", gaps_path), \
                    mock.patch.object(flt, "load_breadcrumbs", return_value=rows), \
                    mock.patch("sys.argv", ["filter.py", str(repo)]), \
                    mock.patch.dict("os.environ", {}, clear=True):
                flt.main()

            findings = [json.loads(line) for line in findings_path.read_text().splitlines()]
            gaps = [json.loads(line) for line in gaps_path.read_text().splitlines()]
            self.assertEqual(
                [f["classification"] for f in findings],
                ["confirmed", "partial", "already-handled", "insufficient-evidence"],
            )
            self.assertEqual([g["classification"] for g in gaps], ["confirmed", "partial"])
            self.assertEqual(findings[0]["evidence_rank"], 0)
            self.assertEqual(findings[1]["evidence_rank"], 1)
            self.assertEqual(set(findings[0]["evidence_chain"]),
                             {"history", "frontier", "repository"})
            validate.assert_called_once()
            self.assertEqual(validate.call_args.args[1], repo.resolve())


if __name__ == "__main__":
    unittest.main()
