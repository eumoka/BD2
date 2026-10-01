import os
import tempfile
import unittest

from minidb.config import PAGE_SIZE
from minidb.storage import DiskManager, Page, PageFullError, RecordCodec
from minidb.storage.page import compute_capacity


class PageTests(unittest.TestCase):
    def setUp(self):
        self.page = Page(0)
        self.page.format(16)

    def test_capacity_is_maximal_and_fits(self):
        cap = compute_capacity(16)
        self.assertEqual(self.page.capacity, cap)
        self.assertLessEqual(6 + (cap + 7) // 8 + cap * 16, PAGE_SIZE)
        self.assertGreater(6 + (cap + 1 + 7) // 8 + (cap + 1) * 16, PAGE_SIZE)

    def test_insert_get_update_delete(self):
        s = self.page.insert(b"a" * 16)
        self.assertEqual(self.page.get(s), b"a" * 16)
        self.page.update(s, b"b" * 16)
        self.assertEqual(self.page.get(s), b"b" * 16)
        self.page.delete(s)
        self.assertEqual(self.page.count, 0)
        with self.assertRaises(KeyError):
            self.page.get(s)

    def test_slot_reuse_after_delete(self):
        a = self.page.insert(b"a" * 16)
        self.page.insert(b"b" * 16)
        self.page.delete(a)
        self.assertEqual(self.page.insert(b"c" * 16), a)

    def test_full_page(self):
        for _ in range(self.page.capacity):
            self.page.insert(b"x" * 16)
        self.assertTrue(self.page.is_full)
        with self.assertRaises(PageFullError):
            self.page.insert(b"x" * 16)

    def test_wrong_size_rejected(self):
        with self.assertRaises(ValueError):
            self.page.insert(b"short")

    def test_records_iterates_used_only(self):
        a = self.page.insert(b"a" * 16)
        self.page.insert(b"b" * 16)
        self.page.delete(a)
        self.assertEqual([r for _, r in self.page.records()], [b"b" * 16])

    def test_oversized_record_rejected(self):
        with self.assertRaises(ValueError):
            Page(0).format(PAGE_SIZE)


class DiskTests(unittest.TestCase):
    def test_persistence_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.db")
            with DiskManager(path) as disk:
                pid = disk.allocate_page()
                p = Page(pid)
                p.format(8)
                p.insert(b"12345678")
                disk.write_page(pid, bytes(p.data))
            with DiskManager(path) as disk:
                self.assertEqual(disk.num_pages, 1)
                p = Page(0, disk.read_page(0))
                self.assertEqual(p.get(0), b"12345678")
            self.assertEqual(os.path.getsize(path), PAGE_SIZE)

    def test_invalid_page(self):
        with tempfile.TemporaryDirectory() as d:
            with DiskManager(os.path.join(d, "t.db")) as disk:
                with self.assertRaises(IndexError):
                    disk.read_page(0)


class CodecTests(unittest.TestCase):
    def test_roundtrip(self):
        c = RecordCodec("<i10s")
        self.assertEqual(c.size, 14)
        self.assertEqual(c.decode(c.encode((7, "ana"))), (7, "ana"))


if __name__ == "__main__":
    unittest.main()
