"""Arquivo de heap: conjunto de páginas com registros de tamanho fixo."""
from typing import Iterator

from .buffer import BufferPool
from .page import RID


class HeapFile:
    def __init__(self, pool: BufferPool, record_size: int):
        self.pool = pool
        self.record_size = record_size
        self._free_pages: list[int] = []  # páginas com espaço livre
        self._load()

    def _load(self) -> None:
        for pid in range(self.pool.disk.num_pages):
            page = self.pool.fetch_page(pid)
            try:
                if page.is_formatted and page.record_size != self.record_size:
                    raise ValueError(
                        f"arquivo usa registros de {page.record_size} bytes, "
                        f"esperado {self.record_size}"
                    )
                if not page.is_formatted or not page.is_full:
                    self._free_pages.append(pid)
            finally:
                self.pool.unpin_page(pid)

    def insert(self, record: bytes) -> RID:
        while self._free_pages:
            pid = self._free_pages[-1]
            page = self.pool.fetch_page(pid)
            if not page.is_formatted:
                page.format(self.record_size)
            if page.is_full:
                self.pool.unpin_page(pid)
                self._free_pages.pop()
                continue
            try:
                slot = page.insert(record)
            except Exception:
                self.pool.unpin_page(pid)
                raise
            if page.is_full:
                self._free_pages.pop()
            self.pool.unpin_page(pid, dirty=True)
            return RID(pid, slot)
        page = self.pool.new_page()
        page.format(self.record_size)
        try:
            slot = page.insert(record)
        except Exception:
            self.pool.unpin_page(page.page_id, dirty=True)
            raise
        if not page.is_full:
            self._free_pages.append(page.page_id)
        self.pool.unpin_page(page.page_id, dirty=True)
        return RID(page.page_id, slot)

    def get(self, rid: RID) -> bytes:
        page = self.pool.fetch_page(rid.page_id)
        try:
            return page.get(rid.slot)
        finally:
            self.pool.unpin_page(rid.page_id)

    def update(self, rid: RID, record: bytes) -> None:
        page = self.pool.fetch_page(rid.page_id)
        try:
            page.update(rid.slot, record)
        except Exception:
            self.pool.unpin_page(rid.page_id)
            raise
        self.pool.unpin_page(rid.page_id, dirty=True)

    def delete(self, rid: RID) -> None:
        page = self.pool.fetch_page(rid.page_id)
        try:
            page.delete(rid.slot)
        except Exception:
            self.pool.unpin_page(rid.page_id)
            raise
        if rid.page_id not in self._free_pages:
            self._free_pages.append(rid.page_id)
        self.pool.unpin_page(rid.page_id, dirty=True)

    def scan(self) -> Iterator[tuple[RID, bytes]]:
        for pid in range(self.pool.disk.num_pages):
            page = self.pool.fetch_page(pid)
            try:
                rows = list(page.records()) if page.is_formatted else []
            finally:
                self.pool.unpin_page(pid)
            for slot, rec in rows:
                yield RID(pid, slot), rec

    def flush(self) -> None:
        self.pool.flush_all()
