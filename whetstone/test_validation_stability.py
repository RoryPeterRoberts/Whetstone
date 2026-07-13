import json
import pathlib
import subprocess
import tempfile
import unittest

import validation


class TestStableRepositoryValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.temp.name)
        self.path = self.repo / "code.py"
        self.path.write_text("value = 1\n")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "code.py"], check=True)
        subprocess.run([
            "git", "-C", str(self.repo), "-c", "user.name=Whetstone",
            "-c", "user.email=whetstone@example.invalid", "commit", "-qm", "fixture",
        ], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_fingerprint_detects_content_change_with_same_dirty_status(self):
        self.path.write_text("value = 2\n")
        first = validation.repository_state(self.repo)
        self.path.write_text("value = 3\n")
        second = validation.repository_state(self.repo)
        self.assertEqual(first["status"], second["status"])
        self.assertNotEqual(first["worktree_sha256"], second["worktree_sha256"])

    def test_repository_change_during_model_pass_fails_every_proposal_closed(self):
        proposals = [
            {"pattern": "a", "current_move": "m", "why": "w"},
            {"pattern": "b", "current_move": "m", "why": "w"},
        ]

        def caller(_repo, _prompt):
            self.path.write_text("value = 2\n")
            return json.dumps([{
                "proposal_id": "P1", "classification": "confirmed", "reason": "reason",
                "repository_evidence": [{
                    "path": "code.py", "line_start": 1, "line_end": 1,
                    "excerpt": "value = 2", "supports": "gap",
                }],
            }])

        results = validation.validate(proposals, self.repo, caller=caller)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["classification"] == "insufficient-evidence" for r in results))
        self.assertTrue(all("changed during validation" in r["reason"] for r in results))


if __name__ == "__main__":
    unittest.main()
