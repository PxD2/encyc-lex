#!/usr/bin/env python3
"""WRBL1 — id+slot stream for LoRa / warble. Book stays off-air."""
from __future__ import annotations

import json
import math
import struct
import sys
import wave
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MAGIC = b"WRB1"
LORA_BYTES = 237
RATE = 16000
NIBBLE_HZ = [800 + i * 80 for i in range(16)]


def crc32_book(data: dict) -> int:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return zlib.crc32(raw) & 0xFFFFFFFF


def load_book(name: str = "phrase") -> dict:
    if name in {"phrase", "sitrep", "phrases"}:
        return json.loads((ROOT / "phrases" / "library.json").read_text())
    if name in {"encyc", "encyclopedia"}:
        p = ROOT / "library.min.json"
        if not p.exists():
            p = ROOT / "library.json"
        if not p.exists():
            rows = []
            for part in sorted((ROOT / "shards").glob("part-*.json")):
                rows.extend(json.loads(part.read_text())["sentences"])
            return {"name": "pxd2-encyc-seed", "version": 2, "sentences": rows}
        return json.loads(p.read_text())
    raise ValueError(f"unknown book {name}")


def fill(tmpl: str, slots: dict) -> str:
    out = tmpl
    for k in ("pct", "n"):
        v = str(slots[k]) if k in slots else "0"
        out = out.replace("{" + k + "}", v)
    return out


def pack(records: list[dict], book: dict, width: int = 1) -> dict:
    crc = crc32_book(book)
    by_id = {int(e["id"]): e for e in book["sentences"]}
    body = b""
    expanded_parts = []
    ids = []
    for rec in records:
        sid = int(rec["id"])
        slots = dict(rec.get("slots") or {})
        entry = by_id.get(sid)
        if not entry:
            raise ValueError(f"unknown id {sid}")
        mask = 0
        extra = b""
        allowed = entry.get("slots") or []
        if "pct" in allowed and "pct" in slots:
            mask |= 1
            extra += bytes([max(0, min(100, int(slots["pct"])))])
        if "n" in allowed and "n" in slots:
            mask |= 2
            extra += struct.pack(">H", max(0, min(65535, int(slots["n"]))))
        body += sid.to_bytes(width, "big") + bytes([mask]) + extra
        ids.append(sid)
        expanded_parts.append(fill(entry["sentence"], slots))
    frame = MAGIC + bytes([width]) + struct.pack(">I", crc) + struct.pack(">H", len(records)) + body
    expanded = " ".join(expanded_parts)
    return {
        "hex": frame.hex(),
        "frame_bytes": len(frame),
        "lora_packets": math.ceil(len(frame) / LORA_BYTES),
        "ids": ids,
        "width": width,
        "library_crc32": f"{crc:08x}",
        "book": book.get("name"),
        "expanded_bytes": len(expanded.encode()),
        "expanded_est_tokens": max(1, len(expanded.split())),
        "frame_vs_utf8_pct": round(100 * len(frame) / max(1, len(expanded.encode())), 2),
        "expanded": expanded,
    }


def unpack(hexstr: str, book: dict) -> dict:
    data = bytes.fromhex(hexstr.replace(" ", ""))
    if data[:4] != MAGIC:
        raise ValueError("not WRB1")
    width = data[4]
    crc = struct.unpack(">I", data[5:9])[0]
    if crc != crc32_book(book):
        raise ValueError("library hash mismatch")
    n = struct.unpack(">H", data[9:11])[0]
    i = 11
    records = []
    for _ in range(n):
        sid = int.from_bytes(data[i : i + width], "big")
        i += width
        mask = data[i]
        i += 1
        slots = {}
        if mask & 1:
            slots["pct"] = data[i]
            i += 1
        if mask & 2:
            slots["n"] = struct.unpack(">H", data[i : i + 2])[0]
            i += 2
        records.append({"id": sid, "slots": slots})
    return pack(records, book, width)


def warble_wav(frame: bytes, path: Path, ms: int = 40) -> Path:
    n_samp = int(RATE * ms / 1000)
    gap = n_samp // 4
    samples = [0] * (RATE // 20)
    for b in frame:
        for nib in ((b >> 4) & 0xF, b & 0xF):
            freq = NIBBLE_HZ[nib]
            for t in range(n_samp):
                samples.append(int(12000 * math.sin(2 * math.pi * freq * t / RATE)))
            samples.extend([0] * gap)
    raw = b"".join(struct.pack("<h", max(-32767, min(32767, s))) for s in samples)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(raw)
    return path


def hear_wav(path: Path, ms: int = 40) -> bytes:
    with wave.open(str(path), "r") as w:
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
    n_samp = int(rate * ms / 1000)
    gap = n_samp // 4
    step = n_samp + gap
    start = rate // 20
    nibs = []
    pos = start
    while pos + n_samp <= len(samples):
        window = samples[pos : pos + n_samp]
        energy = sum(abs(x) for x in window) / max(1, len(window))
        if energy < 400:
            pos += gap
            continue
        best, best_e = 0, -1.0
        for nib, freq in enumerate(NIBBLE_HZ):
            acc = 0.0
            for t, x in enumerate(window):
                acc += x * math.sin(2 * math.pi * freq * t / rate)
            if acc > best_e:
                best_e = acc
                best = nib
        nibs.append(best)
        pos += step
    if len(nibs) % 2:
        nibs = nibs[:-1]
    return bytes((nibs[i] << 4) | nibs[i + 1] for i in range(0, len(nibs), 2))


def capacity(avg_sentence_tokens: float = 20.0, bytes_per_rec: float = 2.2) -> dict:
    header = 11
    recs = int((LORA_BYTES - header) / bytes_per_rec)
    tokens_per_pkt = recs * avg_sentence_tokens
    return {
        "lora_payload_bytes": LORA_BYTES,
        "header_bytes": header,
        "recs_per_237B_est": recs,
        "avg_sentence_tokens": avg_sentence_tokens,
        "expanded_tokens_per_packet": int(tokens_per_pkt),
        "packets_for_1e6_expanded_tokens": math.ceil(1_000_000 / max(1.0, tokens_per_pkt)),
        "note": "record = id + mask + optional pct/n; book already on both radios",
    }


def main() -> None:
    book = load_book("phrase")
    recs = [
        {"id": 1, "slots": {"pct": 94, "n": 7}},
        {"id": 2, "slots": {}},
        {"id": 5, "slots": {"pct": 100}},
        {"id": 6, "slots": {}},
        {"id": 1, "slots": {"pct": 10, "n": 2}},
    ]
    packed = pack(recs, book)
    wav = warble_wav(bytes.fromhex(packed["hex"]), HERE / "sitrep.wav")
    heard = hear_wav(wav)
    ok = heard.hex() == packed["hex"]
    Path(HERE / "RECEIPT.json").write_text(
        json.dumps(
            {
                "sample": {k: packed[k] for k in packed if k != "expanded"},
                "capacity": capacity(),
                "hear_ok": ok,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"hex": packed["hex"], "hear_ok": ok, "expanded": packed["expanded"], "capacity": capacity()}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "hear":
        book = load_book("phrase")
        data = hear_wav(Path(sys.argv[2] if len(sys.argv) > 2 else HERE / "sitrep.wav"))
        print(unpack(data.hex(), book)["expanded"])
    else:
        main()
