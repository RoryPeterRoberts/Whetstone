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


if __name__ == "__main__":
    unittest.main()
