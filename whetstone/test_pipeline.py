import json
import pathlib
import tempfile
import unittest
from unittest import mock

import filter as flt
import runs
import teach
import watch
import whet


class TestEvidencePipeline(unittest.TestCase):
    def test_target_without_patterns_does_not_use_another_repo(self):
        rows = [{"repo": "other", "pattern": "tool calling", "evidence": "x"}]
        self.assertEqual(flt.select(rows, "target", {}), [])

    def test_codex_defaults_are_visible(self):
        with tempfile.TemporaryDirectory() as td:
            config = pathlib.Path(td) / "config.toml"
            config.write_text('model = "gpt-test"\nmodel_reasoning_effort = "high"\n')
            self.assertEqual(whet.codex_defaults(config), {
                "runtime": "Codex CLI", "model": "gpt-test", "reasoning_effort": "high"})

    def test_atomic_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "items.jsonl"
            runs.replace_jsonl(path, [{"a": 1}, {"a": 2}])
            self.assertEqual([json.loads(x)["a"] for x in path.read_text().splitlines()], [1, 2])

    @mock.patch.object(watch, "fetch", side_effect=OSError("offline"))
    def test_watch_preserves_last_good_feed_if_all_sources_fail(self, _fetch):
        with tempfile.TemporaryDirectory() as td:
            original = watch.FRONTIER
            watch.FRONTIER = pathlib.Path(td) / "frontier.jsonl"
            watch.FRONTIER.write_text('{"old": true}\n')
            try:
                with mock.patch("sys.argv", ["watch.py", "1"]):
                    with self.assertRaises(RuntimeError):
                        watch.main()
                self.assertEqual(watch.FRONTIER.read_text(), '{"old": true}\n')
            finally:
                watch.FRONTIER = original

    @mock.patch.object(whet, "_run", side_effect=RuntimeError("stage failed"))
    @mock.patch.object(whet, "_head", return_value="abc")
    @mock.patch.object(runs, "append")
    def test_failed_stage_records_failure_and_stops(self, append, _head, _run):
        with self.assertRaises(RuntimeError):
            whet.learn(".")
        record = append.call_args.args[0]
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["stages"][-1]["status"], "failed")

    @mock.patch.object(whet, "learn", return_value={"status": "complete"})
    @mock.patch.object(whet, "_run")
    def test_prepare_refreshes_frontier_before_learning(self, run, learn):
        result = whet.prepare("/repo", 9, 2)
        run.assert_called_once_with("watch.py")
        learn.assert_called_once_with("/repo", 9, 2, frontier_refreshed=True)
        self.assertEqual(result["status"], "complete")

    @mock.patch.object(whet, "learn")
    @mock.patch.object(whet, "_run", side_effect=RuntimeError("frontier unavailable"))
    def test_prepare_stops_if_frontier_refresh_fails(self, _run, learn):
        with self.assertRaises(RuntimeError):
            whet.prepare("/repo")
        learn.assert_not_called()

    def test_disappearing_gap_requires_verification(self):
        with tempfile.TemporaryDirectory() as td:
            taught = pathlib.Path(td) / "taught.jsonl"
            gaps = pathlib.Path(td) / "gaps.jsonl"
            taught.write_text(json.dumps({"project": "p", "pattern": "x", "status": "open"}) + "\n")
            original_taught, original_gaps = teach.TAUGHT, teach.GAPS
            teach.TAUGHT, teach.GAPS = taught, gaps
            try:
                self.assertEqual(teach.mark_needs_verification("p"), ["x"])
                self.assertEqual(json.loads(taught.read_text())["status"], "needs_verification")
            finally:
                teach.TAUGHT, teach.GAPS = original_taught, original_gaps


if __name__ == "__main__":
    unittest.main()
