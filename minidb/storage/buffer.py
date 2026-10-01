"""M2: cache de páginas com pin/unpin, página suja e substituição LRU."""
from collections import OrderedDict

from .disk import DiskManager
from .page import Page


class BufferPoolFullError(Exception):
    """Todas as páginas em memória estão fixadas (pinned)."""


class _Frame:
    __slots__ = ("page", "pin_count", "dirty")

    def __init__(self, page: Page):
        self.page = page
        self.pin_count = 0
        self.dirty = False


class BufferPool:
    def __init__(self, disk: DiskManager, capacity: int = 8):
        if capacity < 1:
            raise ValueError("capacity deve ser >= 1")
        self.disk = disk
        self.capacity = capacity
        self._frames: OrderedDict[int, _Frame] = OrderedDict()  # ordem = LRU
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._frames)

    def __contains__(self, page_id: int) -> bool:
        return page_id in self._frames

    def fetch_page(self, page_id: int) -> Page:
        """Devolve a página fixada. O chamador deve chamar unpin_page."""
        frame = self._frames.get(page_id)
        if frame is not None:
            self.hits += 1
            self._frames.move_to_end(page_id)
        else:
            self.misses += 1
            self._make_room()
            frame = _Frame(Page(page_id, self.disk.read_page(page_id)))
            self._frames[page_id] = frame
        frame.pin_count += 1
        return frame.page

    def new_page(self) -> Page:
        """Aloca uma página nova no arquivo e a devolve fixada."""
        self._make_room()
        page_id = self.disk.allocate_page()
        frame = _Frame(Page(page_id))
        frame.pin_count = 1
        self._frames[page_id] = frame
        return frame.page

    def unpin_page(self, page_id: int, dirty: bool = False) -> None:
        frame = self._frames[page_id]
        if frame.pin_count == 0:
            raise ValueError(f"página {page_id} não está fixada")
        frame.pin_count -= 1
        frame.dirty = frame.dirty or dirty

    def is_dirty(self, page_id: int) -> bool:
        return self._frames[page_id].dirty

    def pin_count(self, page_id: int) -> int:
        return self._frames[page_id].pin_count

    def flush_page(self, page_id: int) -> None:
        frame = self._frames[page_id]
        if frame.dirty:
            self.disk.write_page(page_id, bytes(frame.page.data))
            frame.dirty = False

    def flush_all(self) -> None:
        for page_id in self._frames:
            self.flush_page(page_id)
        self.disk.sync()

    def _make_room(self) -> None:
        if len(self._frames) < self.capacity:
            return
        for page_id, frame in self._frames.items():  # do menos ao mais recente
            if frame.pin_count == 0:
                self.flush_page(page_id)
                del self._frames[page_id]
                return
        raise BufferPoolFullError("todas as páginas estão fixadas")
