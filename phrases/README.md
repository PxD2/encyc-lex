# pxd2-phrase-sitrep

Aligned English surfaces collapse to one meaning id.

`how's it going` / `how you doing` / `what's happening` / `what's going on` / `sitrep` → **id 1**.

Wire is LEX1 hex. Receiver expands from this book (`library_crc32` e454a667).

```
python3 codec.py "whats up"
python3 codec.py "sitrep 94 percent node 7"
```

Open `gui.html` next to `library.json` (local server if fetch is blocked).
