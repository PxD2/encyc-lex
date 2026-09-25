# pxd2-encyc-seed

Closed encyclopedia book for Numerical Sentencing / LEX1.

Not the `PxD2/lex` demo library. Not a Wikipedia dump.

- book: `library.json`
- compact book: `library.min.json`
- sequential index: `INDEX.tsv`
- codec helper: `index.py`
- receipt: `RECEIPT.json`
- sample frames: `FRAMES.json`

```
python3 index.py
```

v2: ids 1–200, width 1, `library_crc32` c43be90f.

Refuse a frame if crc mismatches. Sync the book before the next sentence.
