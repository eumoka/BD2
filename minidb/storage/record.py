"""Codificação de tuplas em registros de tamanho fixo (struct)."""
import struct


class RecordCodec:
    """Ex.: RecordCodec("<i20s") codifica (int, str) em 24 bytes.

    Campos 's' aceitam str (UTF-8, preenchida com zeros) e voltam como str.
    """

    def __init__(self, fmt: str):
        self._struct = struct.Struct(fmt)
        self._str_fields = [i for i, c in enumerate(_field_codes(fmt)) if c == "s"]

    @property
    def size(self) -> int:
        return self._struct.size

    def encode(self, values: tuple) -> bytes:
        vals = list(values)
        for i in self._str_fields:
            if isinstance(vals[i], str):
                vals[i] = vals[i].encode("utf-8")
        return self._struct.pack(*vals)

    def decode(self, raw: bytes) -> tuple:
        vals = list(self._struct.unpack(raw))
        for i in self._str_fields:
            vals[i] = vals[i].rstrip(b"\x00").decode("utf-8")
        return tuple(vals)


def _field_codes(fmt: str) -> list[str]:
    codes, num = [], ""
    for ch in fmt.lstrip("@=<>!"):
        if ch.isdigit():
            num += ch
        elif ch == "s":
            codes.append("s")
            num = ""
        elif not ch.isspace():
            codes.extend([ch] * (int(num) if num else 1))
            num = ""
    return codes
