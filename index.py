#!/usr/bin/env python3
"""Sequential encyclopedia index. Closed book. Not the internet."""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAGIC = b"LEX1"


def load(path: Path | None = None) -> dict:
    p = path or HERE / "library.json"
    if not p.exists():
        p = HERE / "library.min.json"
    return json.loads(p.read_text())


def crc32_book(data: dict) -> int:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return zlib.crc32(raw) & 0xFFFFFFFF


def width_for(max_id: int) -> int:
    if max_id <= 255:
        return 1
    if max_id <= 65535:
        return 2
    return 4


def stats(data: dict) -> dict:
    rows = data["sentences"]
    n = len(rows)
    max_id = max(int(r["id"]) for r in rows)
    w = width_for(max_id)
    texts = [r["sentence"] for r in rows]
    utf8 = sum(len(t.encode()) for t in texts)
    avg = utf8 / max(1, n)
    book_bytes = len(json.dumps(data, sort_keys=True, separators=(",", ":")).encode())
    return {
        "name": data.get("name"),
        "version": data.get("version"),
        "sentences": n,
        "max_id": max_id,
        "recommended_width": w,
        "book_compact_bytes": book_bytes,
        "avg_sentence_utf8": round(avg, 1),
        "sum_sentence_utf8": utf8,
        "wire_bytes_per_hit": 4 + 1 + 4 + w + 1,
        "library_crc32": f"{crc32_book(data):08x}",
        "note": "wire savings only after both ends already hold this book",
    }


def encode_id(sid: int, data: dict, slots: dict | None = None) -> dict:
    slots = slots or {}
    by_id = {int(e["id"]): e for e in data["sentences"]}
    entry = by_id[sid]
    w = width_for(max(by_id))
    mask = 0
    extra = b""
    if "pct" in entry.get("slots", []) and "pct" in slots:
        mask |= 1
        extra += bytes([max(0, min(100, int(slots["pct"])))])
    if "n" in entry.get("slots", []) and "n" in slots:
        mask |= 2
        extra += struct.pack(">H", max(0, min(65535, int(slots["n"]))))
    frame = MAGIC + bytes([w]) + struct.pack(">I", crc32_book(data)) + sid.to_bytes(w, "big") + bytes([mask]) + extra
    sent = entry["sentence"]
    for k, v in slots.items():
        sent = sent.replace("{" + k + "}", str(v))
    return {
        "id": sid,
        "hex": frame.hex(),
        "frame_bytes": len(frame),
        "utf8_bytes": len(sent.encode()),
        "frame_vs_utf8_pct": round(100 * len(frame) / max(1, len(sent.encode())), 2),
        "sentence": sent,
        "library_crc32": f"{crc32_book(data):08x}",
    }


def main() -> None:
    data = load()
    s = stats(data)
    Path(HERE / "RECEIPT.json").write_text(json.dumps(s, indent=2) + "\n")
    sample = [encode_id(1, data), encode_id(56, data, {"n": 56}), encode_id(59, data, {"pct": 8})]
    Path(HERE / "FRAMES.json").write_text(json.dumps(sample, indent=2) + "\n")
    print(json.dumps(s, indent=2))
    print("--- sample frames ---")
    for f in sample:
        print(f["id"], f["hex"], f["frame_vs_utf8_pct"], "% of utf8")


if __name__ == "__main__":
    main()
