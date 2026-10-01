"""M1: leitura e escrita de páginas inteiras em um arquivo de dados."""
import os

from ..config import PAGE_SIZE


class DiskManager:
    def __init__(self, path: str):
        self.path = path
        mode = "r+b" if os.path.exists(path) else "w+b"
        self._f = open(path, mode)
        self.reads = 0
        self.writes = 0

    @property
    def num_pages(self) -> int:
        self._f.seek(0, os.SEEK_END)
        return self._f.tell() // PAGE_SIZE

    def allocate_page(self) -> int:
        """Acrescenta uma página zerada ao arquivo (não conta como escrita de dados)."""
        page_id = self.num_pages
        self._f.seek(page_id * PAGE_SIZE)
        self._f.write(bytes(PAGE_SIZE))
        self._f.flush()
        return page_id

    def read_page(self, page_id: int) -> bytearray:
        if not 0 <= page_id < self.num_pages:
            raise IndexError(f"página {page_id} não existe")
        self._f.seek(page_id * PAGE_SIZE)
        self.reads += 1
        return bytearray(self._f.read(PAGE_SIZE))

    def write_page(self, page_id: int, data: bytes) -> None:
        if len(data) != PAGE_SIZE:
            raise ValueError("página com tamanho inválido")
        self._f.seek(page_id * PAGE_SIZE)
        self._f.write(data)
        self._f.flush()
        self.writes += 1

    def sync(self) -> None:
        self._f.flush()
        os.fsync(self._f.fileno())

    def close(self) -> None:
        if not self._f.closed:
            self.sync()
            self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
