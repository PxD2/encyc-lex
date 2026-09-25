# encyc-lex

Public closed books + wire for Numerical Sentencing.

Not `PxD2/lex` demo. Not `cyrptonics-lab` private directory.

| layer | path | what |
| --- | --- | --- |
| encyclopedia | `shards/` + `stitch.py` | ids 1–200 definitions |
| phrases | `phrases/` | 114 surfaces → 10 meaning ids |
| warble / LoRa | `warble/wrbl.py` | WRB1 id+slot stream + WAV hear |
| tests | `tests/test_roundtrip.py` | phrase, shards, warble hear |

```
python3 phrases/codec.py "whats up"
python3 warble/wrbl.py
python3 warble/wrbl.py hear warble/sitrep.wav
python3 tests/test_roundtrip.py
python3 stitch.py
```

Two books. Same numeric id in phrase ≠ encyclopedia. WRB1 carries `lib_crc32`; refuse on mismatch.
