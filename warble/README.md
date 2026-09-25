# WRBL1

Id stream for LoRa / warble. The book is not on the air.

```
WRB1 | width u8 | lib_crc32 u32be | count u16be | ids…
```

237-byte LoRa payload, width 1: **226 ids** after an 11-byte header.

Expanded size = ids × tokens already stored in the shared book.

```
python3 wrbl.py
```

Writes `sitrep.wav`: each nibble is a tone 800+80n Hz. Number is the frequency.

Private directory + MAC warble stays in `cyrptonics-lab`. This pack uses the public phrase book only.
