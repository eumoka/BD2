# BD2 — minidb

Um sistema gerenciador de banco de dados pequeno, construído do zero em Python,
para entender o que acontece entre escrever uma consulta e receber o resultado.

## Módulos

| # | Módulo | Estado |
|---|--------|--------|
| M1 | Página e arquivo de dados (registros de tamanho fixo) | feito |
| M2 | Cache de páginas (pin/unpin, página suja, LRU) | feito |
| M3 | Árvore B+ | pendente |
| M4 | Parser e catálogo | pendente |
| M5 | Executor (modelo iterador) | pendente |
| M6 | Transações (BEGIN/COMMIT/ROLLBACK) | pendente |
| M7 | Recuperação (WAL, redo/undo) | pendente |

## Estrutura

```
minidb/
  config.py          # PAGE_SIZE = 4096
  storage/
    page.py          # Page (bitmap de slots) e RID
    record.py        # RecordCodec (tupla <-> bytes de tamanho fixo)
    disk.py          # DiskManager: lê/escreve páginas inteiras
    buffer.py        # BufferPool: cache LRU com pin e dirty
    heap.py          # HeapFile: insert/get/update/delete/scan
tests/
```

## Uso rápido

```python
from minidb.storage import BufferPool, DiskManager, HeapFile, RecordCodec

codec = RecordCodec("<i20s")
disk = DiskManager("dados.db")
heap = HeapFile(BufferPool(disk, capacity=8), codec.size)

rid = heap.insert(codec.encode((1, "ana")))
print(codec.decode(heap.get(rid)))   # (1, 'ana')
heap.flush(); disk.close()
```

## Testes

```bash
python -m unittest discover -v
```
