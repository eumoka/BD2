import os
import tempfile
import unittest

from minidb.storage import (
    BufferPool,
    BufferPoolFullError,
    DiskManager,
    HeapFile,
    RecordCodec,
)


class BufferPoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.disk = DiskManager(os.path.join(self.tmp.name, "t.db"))
        for _ in range(5):
            self.disk.allocate_page()

    def tearDown(self):
        self.disk.close()
        self.tmp.cleanup()

    def test_hit_and_miss(self):
        pool = BufferPool(self.disk, 2)
        pool.fetch_page(0)
        pool.unpin_page(0)
        pool.fetch_page(0)
        pool.unpin_page(0)
        self.assertEqual((pool.hits, pool.misses), (1, 1))

    def test_lru_eviction_order(self):
        pool = BufferPool(self.disk, 2)
        for pid in (0, 1):
            pool.fetch_page(pid)
            pool.unpin_page(pid)
        pool.fetch_page(0)  # a página 1 passa a ser a menos recente
        pool.unpin_page(0)
        pool.fetch_page(2)
        pool.unpin_page(2)
        self.assertIn(0, pool)
        self.assertNotIn(1, pool)

    def test_dirty_page_written_on_eviction(self):
        pool = BufferPool(self.disk, 1)
        p = pool.fetch_page(0)
        p.format(8)
        p.insert(b"abcdefgh")
        pool.unpin_page(0, dirty=True)
        self.assertTrue(pool.is_dirty(0))
        writes = self.disk.writes
        pool.fetch_page(1)  # expulsa a página 0
        pool.unpin_page(1)
        self.assertEqual(self.disk.writes, writes + 1)
        self.assertEqual(pool.fetch_page(0).get(0), b"abcdefgh")

    def test_clean_page_not_written(self):
        pool = BufferPool(self.disk, 1)
        pool.fetch_page(0)
        pool.unpin_page(0)
        writes = self.disk.writes
        pool.fetch_page(1)
        pool.unpin_page(1)
        self.assertEqual(self.disk.writes, writes)

    def test_pinned_pages_not_evicted(self):
        pool = BufferPool(self.disk, 2)
        pool.fetch_page(0)
        pool.fetch_page(1)
        with self.assertRaises(BufferPoolFullError):
            pool.fetch_page(2)
        pool.unpin_page(0)
        pool.fetch_page(2)
        self.assertNotIn(0, pool)

    def test_flush_clears_dirty(self):
        pool = BufferPool(self.disk, 2)
        p = pool.fetch_page(0)
        p.format(8)
        p.insert(b"abcdefgh")
        pool.unpin_page(0, dirty=True)
        pool.flush_all()
        self.assertFalse(pool.is_dirty(0))

    def test_unpin_without_pin_fails(self):
        pool = BufferPool(self.disk, 2)
        pool.fetch_page(0)
        pool.unpin_page(0)
        with self.assertRaises(ValueError):
            pool.unpin_page(0)


class HeapFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "h.db")
        self.codec = RecordCodec("<i20s")

    def tearDown(self):
        self.tmp.cleanup()

    def open(self, capacity=3):
        disk = DiskManager(self.path)
        return disk, HeapFile(BufferPool(disk, capacity), self.codec.size)

    def test_many_inserts_span_pages_with_small_pool(self):
        disk, heap = self.open(capacity=2)
        rids = [heap.insert(self.codec.encode((i, f"n{i}"))) for i in range(500)]
        self.assertGreater(disk.num_pages, 1)
        for i in (0, 123, 499):
            self.assertEqual(self.codec.decode(heap.get(rids[i])), (i, f"n{i}"))
        self.assertEqual(sum(1 for _ in heap.scan()), 500)
        heap.flush()
        disk.close()

    def test_persistence_after_flush(self):
        disk, heap = self.open()
        for i in range(100):
            heap.insert(self.codec.encode((i, "x")))
        heap.flush()
        disk.close()
        disk, heap = self.open()
        ids = sorted(self.codec.decode(r)[0] for _, r in heap.scan())
        self.assertEqual(ids, list(range(100)))
        disk.close()

    def test_delete_and_space_reuse(self):
        disk, heap = self.open()
        rids = [heap.insert(self.codec.encode((i, "x"))) for i in range(10)]
        pages = disk.num_pages
        heap.delete(rids[3])
        with self.assertRaises(KeyError):
            heap.get(rids[3])
        self.assertEqual(heap.insert(self.codec.encode((99, "y"))), rids[3])
        self.assertEqual(disk.num_pages, pages)
        disk.close()

    def test_update(self):
        disk, heap = self.open()
        rid = heap.insert(self.codec.encode((1, "a")))
        heap.update(rid, self.codec.encode((1, "b")))
        self.assertEqual(self.codec.decode(heap.get(rid)), (1, "b"))
        disk.close()

    def test_no_pin_leaks(self):
        disk, heap = self.open(capacity=1)  # qualquer vazamento de pin estoura
        for i in range(300):
            heap.insert(self.codec.encode((i, "x")))
        list(heap.scan())
        disk.close()

    def test_record_size_mismatch(self):
        disk, heap = self.open()
        heap.insert(self.codec.encode((1, "a")))
        heap.flush()
        disk.close()
        disk = DiskManager(self.path)
        with self.assertRaises(ValueError):
            HeapFile(BufferPool(disk, 2), 8)
        disk.close()


if __name__ == "__main__":
    unittest.main()
