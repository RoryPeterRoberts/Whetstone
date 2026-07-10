import json, unittest, tempfile, pathlib
from unittest import mock
import canon
import filter as flt


class TestSelectRecurrence(unittest.TestCase):
    def test_recurrence_counts_by_canon(self):
        rows = [
            {"repo": "A", "pattern": "structured JSON output", "evidence": "x"},
            {"repo": "B", "pattern": "schema-constrained outputs", "evidence": "y"},
        ]
        cmap = {"structured JSON output": "structured-output-contract",
                "schema-constrained outputs": "structured-output-contract"}
        out = flt.select(rows, None, cmap)
        self.assertEqual(len(out), 2)                       # two distinct free-text patterns
        for p in out:
            self.assertEqual(p["n_repos"], 2)               # both share one canon -> recurs across 2 repos
            self.assertEqual(p["canon"], "structured-output-contract")

    def test_backcompat_without_cmap(self):
        rows = [{"repo": "A", "pattern": "P", "evidence": ""},
                {"repo": "B", "pattern": "P", "evidence": ""}]
        out = flt.select(rows, None)
        self.assertEqual(out[0]["n_repos"], 2)              # identical free-text still counts


class TestCanon(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = (canon.CANON, canon.CANON_MAP)
        canon.CANON = pathlib.Path(self.tmp) / "canon.jsonl"
        canon.CANON_MAP = pathlib.Path(self.tmp) / "canon_map.jsonl"
        canon.CANON.write_text(
            json.dumps({"id": "structured-output-contract", "name": "Structured output", "blurb": ""}) + "\n")

    def tearDown(self):
        canon.CANON, canon.CANON_MAP = self._orig

    @mock.patch("canon.call_codex")
    def test_maps_to_existing_then_caches(self, cc):
        cc.return_value = '{"structured JSON output": "structured-output-contract"}'
        m = canon.canonicalize(["structured JSON output"])
        self.assertEqual(m["structured JSON output"], "structured-output-contract")
        # second call for the same pattern must hit the cache, not the model
        cc.side_effect = AssertionError("codex called for an already-cached pattern")
        m2 = canon.canonicalize(["structured JSON output"])
        self.assertEqual(m2["structured JSON output"], "structured-output-contract")

    @mock.patch("canon.call_codex")
    def test_proposes_new_canon_without_mutating_seed(self, cc):
        cc.return_value = '{"some novel trick": "novel-trick"}'
        before = canon.CANON.read_text()
        m = canon.canonicalize(["some novel trick"])
        self.assertEqual(m["some novel trick"], "novel-trick")
        self.assertEqual(canon.CANON.read_text(), before)

    def test_empty_input(self):
        self.assertEqual(canon.canonicalize([]), {})


class TestPromptV2(unittest.TestCase):
    def test_not_a_gap_anchors_present(self):
        self.assertIn("NOT gaps", flt.PROMPT)
        self.assertIn("type hints", flt.PROMPT)

    def test_deficiency_rule_present(self):
        self.assertIn("specifically lacks", flt.PROMPT)
        self.assertIn("not merely that the topic", flt.PROMPT)

    def test_prompt_still_formats(self):
        # the added rules must not break the .format() placeholders
        flt.PROMPT.format(patterns="p", frontier="f")


class TestWorstOfN(unittest.TestCase):
    @mock.patch("judge_eval.flt.judge")
    @mock.patch("judge_eval.load_golden")
    def test_any_run_must_fail_flags_not_calibrated(self, lg, jm):
        import judge_eval
        lg.return_value = [{"pattern": "P", "evidence": "", "expect": False, "must": True}]
        # 3 runs: clean, clean, then a must-case over-flag
        jm.side_effect = [
            [{"pattern": "P", "gap": False}],
            [{"pattern": "P", "gap": False}],
            [{"pattern": "P", "gap": True}],
        ]
        self.assertEqual(judge_eval.run(3), 1)   # worst-of-3 catches the failing run

    @mock.patch("judge_eval.flt.judge")
    @mock.patch("judge_eval.load_golden")
    def test_all_runs_clean_passes(self, lg, jm):
        import judge_eval
        lg.return_value = [{"pattern": "P", "evidence": "", "expect": False, "must": True}]
        jm.side_effect = [[{"pattern": "P", "gap": False}]] * 3
        self.assertEqual(judge_eval.run(3), 0)

    @mock.patch("judge_eval.flt.judge")
    @mock.patch("judge_eval.load_golden")
    def test_bad_run_first_still_flagged(self, lg, jm):
        import judge_eval
        lg.return_value = [{"pattern": "P", "evidence": "", "expect": False, "must": True}]
        # failing run is FIRST — a "keep-the-last-run" bug would wrongly certify this
        jm.side_effect = [
            [{"pattern": "P", "gap": True}],   # must-case over-flag (fail)
            [{"pattern": "P", "gap": False}],
            [{"pattern": "P", "gap": False}],
        ]
        self.assertEqual(judge_eval.run(3), 1)
