#!/usr/bin/env python3
"""WRBL1 — id stream for LoRa / warble. Book stays off-air."""
from __future__ import annotations

import json
import math
import struct
import wave
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAGIC = b"WRB1"
LORA_BYTES = 237
RATE = 16000


def crc32_book(data: dict) -> int:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return zlib.crc32(raw) & 0xFFFFFFFF


def load_phrase() -> dict:
    return json.loads((HERE.parent / "phrases" / "library.json").read_text())


def pack(ids: list[int], book: dict, width: int = 1) -> dict:
    crc = crc32_book(book)
    body = b"".join(int(i).to_bytes(width, "big") for i in ids)
    frame = MAGIC + bytes([width]) + struct.pack(">I", crc) + struct.pack(">H", len(ids)) + body
    n_pkt = math.ceil(len(frame) / LORA_BYTES)
    by_id = {int(e["id"]): e for e in book["sentences"]}
    expanded = " ".join(by_id[int(i)]["sentence"] for i in ids if int(i) in by_id)
    return {
        "hex": frame.hex(),
        "frame_bytes": len(frame),
        "lora_packets": n_pkt,
        "ids": ids,
        "width": width,
        "library_crc32": f"{crc:08x}",
        "expanded_bytes": len(expanded.encode()),
        "expanded_est_tokens": max(1, len(expanded.split())),
        "frame_vs_utf8_pct": round(100 * len(frame) / max(1, len(expanded.encode())), 2),
        "expanded": expanded,
    }


def unpack(hexstr: str, book: dict) -> dict:
    data = bytes.fromhex(hexstr)
    if data[:4] != MAGIC:
        raise ValueError("not WRB1")
    width = data[4]
    crc = struct.unpack(">I", data[5:9])[0]
    if crc != crc32_book(book):
        raise ValueError("library hash mismatch")
    n = struct.unpack(">H", data[9:11])[0]
    body = data[11:]
    ids = [int.from_bytes(body[i : i + width], "big") for i in range(0, n * width, width)]
    return pack(ids, book, width)


def warble_wav(frame: bytes, path: Path, ms: int = 40) -> Path:
    n_samp = int(RATE * ms / 1000)
    samples = []
    samples.extend([0] * (RATE // 20))
    for b in frame:
        for nib in ((b >> 4) & 0xF, b & 0xF):
            freq = 800 + nib * 80
            for i in range(n_samp):
                samples.append(int(12000 * math.sin(2 * math.pi * freq * i / RATE)))
            samples.extend([0] * (n_samp // 4))
    raw = b"".join(struct.pack("<h", max(-32767, min(32767, s))) for s in samples)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(raw)
    return path


def capacity(avg_sentence_tokens: float = 20.0, width: int = 1) -> dict:
    header = 4 + 1 + 4 + 2
    ids_per_pkt = (LORA_BYTES - header) // width
    tokens_per_pkt = ids_per_pkt * avg_sentence_tokens
    pkts_for_1m = math.ceil(1_000_000 / max(1.0, tokens_per_pkt))
    return {
        "lora_payload_bytes": LORA_BYTES,
        "header_bytes": header,
        "ids_per_237B": ids_per_pkt,
        "avg_sentence_tokens": avg_sentence_tokens,
        "expanded_tokens_per_packet": int(tokens_per_pkt),
        "packets_for_1e6_expanded_tokens": pkts_for_1m,
        "note": "1e6 is expanded tokens after the book is already on both radios, not novel UTF-8",
    }


if __name__ == "__main__":
    book = load_phrase()
    packed = pack([1, 2, 5, 6, 1], book)
    Path(HERE / "RECEIPT.json").write_text(
        json.dumps({"sample": {k: packed[k] for k in packed if k != "expanded"}, "capacity": capacity()}, indent=2)
        + "\n"
    )
    wav = warble_wav(bytes.fromhex(packed["hex"]), HERE / "sitrep.wav")
    print(json.dumps({"hex": packed["hex"], "frame_bytes": packed["frame_bytes"], "wav": str(wav), "capacity": capacity()}, indent=2))
    print(packed["expanded"])
