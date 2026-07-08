import json, unittest, tempfile, pathlib
from unittest import mock
import canon


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
    def test_proposes_and_appends_new_canon(self, cc):
        cc.return_value = '{"some novel trick": "novel-trick"}'
        m = canon.canonicalize(["some novel trick"])
        self.assertEqual(m["some novel trick"], "novel-trick")
        self.assertIn("novel-trick", {c["id"] for c in canon.load_canon()})

    def test_empty_input(self):
        self.assertEqual(canon.canonicalize([]), {})
