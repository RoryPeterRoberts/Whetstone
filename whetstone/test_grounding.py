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


if __name__ == "__main__":
    unittest.main()
