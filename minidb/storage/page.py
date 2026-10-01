"""M1: página de tamanho fixo contendo registros de tamanho fixo.

Layout da página:

    [record_size:u16][capacity:u16][count:u16][bitmap: ceil(capacity/8) bytes][slot 0][slot 1]...

O bitmap marca quais slots estão ocupados.
"""
import struct
from typing import Iterator, NamedTuple

from ..config import PAGE_SIZE

_HEADER = struct.Struct("<HHH")


class RID(NamedTuple):
    """Identificador de registro: página + slot."""

    page_id: int
    slot: int


class PageFullError(Exception):
    pass


def compute_capacity(record_size: int, page_size: int = PAGE_SIZE) -> int:
    if record_size <= 0:
        raise ValueError("record_size deve ser positivo")
    n = (page_size - _HEADER.size) // record_size
    while n > 0 and _HEADER.size + (n + 7) // 8 + n * record_size > page_size:
        n -= 1
    if n == 0:
        raise ValueError("registro não cabe em uma página")
    return n


class Page:
    def __init__(self, page_id: int, data: bytearray | None = None):
        self.page_id = page_id
        self.data = data if data is not None else bytearray(PAGE_SIZE)
        if len(self.data) != PAGE_SIZE:
            raise ValueError("página com tamanho inválido")

    # --- cabeçalho -------------------------------------------------------
    @property
    def is_formatted(self) -> bool:
        return self.record_size != 0

    @property
    def record_size(self) -> int:
        return _HEADER.unpack_from(self.data, 0)[0]

    @property
    def capacity(self) -> int:
        return _HEADER.unpack_from(self.data, 0)[1]

    @property
    def count(self) -> int:
        return _HEADER.unpack_from(self.data, 0)[2]

    def _set_count(self, n: int) -> None:
        _HEADER.pack_into(self.data, 0, self.record_size, self.capacity, n)

    @property
    def is_full(self) -> bool:
        return self.count >= self.capacity

    def format(self, record_size: int) -> None:
        cap = compute_capacity(record_size)
        self.data[:] = bytes(PAGE_SIZE)
        _HEADER.pack_into(self.data, 0, record_size, cap, 0)

    # --- slots -----------------------------------------------------------
    def _slot_off(self, slot: int) -> int:
        return _HEADER.size + (self.capacity + 7) // 8 + slot * self.record_size

    def _check_slot(self, slot: int) -> None:
        if not 0 <= slot < self.capacity:
            raise IndexError(f"slot {slot} fora do intervalo")

    def is_used(self, slot: int) -> bool:
        self._check_slot(slot)
        return bool(self.data[_HEADER.size + slot // 8] & (1 << (slot % 8)))

    def _set_used(self, slot: int, used: bool) -> None:
        i = _HEADER.size + slot // 8
        if used:
            self.data[i] |= 1 << (slot % 8)
        else:
            self.data[i] &= ~(1 << (slot % 8))

    # --- operações -------------------------------------------------------
    def insert(self, record: bytes) -> int:
        if len(record) != self.record_size:
            raise ValueError(
                f"registro deve ter {self.record_size} bytes, recebeu {len(record)}"
            )
        for slot in range(self.capacity):
            if not self.is_used(slot):
                off = self._slot_off(slot)
                self.data[off : off + self.record_size] = record
                self._set_used(slot, True)
                self._set_count(self.count + 1)
                return slot
        raise PageFullError(f"página {self.page_id} cheia")

    def get(self, slot: int) -> bytes:
        if not self.is_used(slot):
            raise KeyError(f"slot {slot} vazio")
        off = self._slot_off(slot)
        return bytes(self.data[off : off + self.record_size])

    def update(self, slot: int, record: bytes) -> None:
        if len(record) != self.record_size:
            raise ValueError("tamanho de registro inválido")
        if not self.is_used(slot):
            raise KeyError(f"slot {slot} vazio")
        off = self._slot_off(slot)
        self.data[off : off + self.record_size] = record

    def delete(self, slot: int) -> None:
        if not self.is_used(slot):
            raise KeyError(f"slot {slot} vazio")
        off = self._slot_off(slot)
        self.data[off : off + self.record_size] = bytes(self.record_size)
        self._set_used(slot, False)
        self._set_count(self.count - 1)

    def records(self) -> Iterator[tuple[int, bytes]]:
        for slot in range(self.capacity):
            if self.is_used(slot):
                yield slot, self.get(slot)
