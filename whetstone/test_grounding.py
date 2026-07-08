import unittest
from unittest import mock
import filter as flt


class TestIndex(unittest.TestCase):
    def test_index_assigns_ids_and_map(self):
        items = [{"source": "A", "title": "t1", "link": "u1"},
                 {"source": "B", "title": "t2", "link": "u2"}]
        digest, id_map = flt._index(items)
        self.assertIn("F1", digest)
        self.assertIn("F2", digest)
        self.assertIn("t1", digest)
        self.assertEqual(id_map["F1"]["title"], "t1")
        self.assertEqual(id_map["F2"]["link"], "u2")

    def test_index_empty(self):
        digest, id_map = flt._index([])
        self.assertEqual(id_map, {})

    def test_frontier_index_skips_non_dict(self):
        import tempfile, pathlib
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write('{"source":"A","title":"t","link":"u"}\n42\n"x"\n')
            tmp = f.name
        orig = flt.FRONTIER
        flt.FRONTIER = pathlib.Path(tmp)
        try:
            digest, id_map = flt.frontier_index()
            self.assertEqual(list(id_map.keys()), ["F1"])
        finally:
            flt.FRONTIER = orig


class TestGround(unittest.TestCase):
    def setUp(self):
        self.id_map = {"F1": {"source": "A", "title": "t1", "link": "u1"}}

    def test_strips_fabricated(self):
        gaps = [{"source_ids": ["F1", "F99"]}]
        flt.ground(gaps, self.id_map)
        self.assertEqual(gaps[0]["source_ids"], ["F1"])
        self.assertTrue(gaps[0]["grounded"])
        self.assertEqual(gaps[0]["sources"][0]["title"], "t1")

    def test_all_fabricated_is_unverified(self):
        gaps = [{"source_ids": ["F99"]}]
        flt.ground(gaps, self.id_map)
        self.assertEqual(gaps[0]["source_ids"], [])
        self.assertFalse(gaps[0]["grounded"])
        self.assertEqual(gaps[0]["sources"], [])

    def test_empty_is_allowed(self):
        gaps = [{"source_ids": []}]
        flt.ground(gaps, self.id_map)
        self.assertFalse(gaps[0]["grounded"])

    def test_missing_key_is_allowed(self):
        gaps = [{"pattern": "p"}]
        flt.ground(gaps, self.id_map)
        self.assertFalse(gaps[0]["grounded"])
        self.assertEqual(gaps[0]["source_ids"], [])


if __name__ == "__main__":
    unittest.main()
