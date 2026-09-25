#!/usr/bin/env python3
"""Map many aligned English surfaces to one LEX1 id."""
from __future__ import annotations

import json
import re
import struct
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAGIC = b"LEX1"


def _norm(s: str) -> str:
    s = s.lower().replace("'", "")
    return re.sub(r"[^a-z0-9%.\s]+", " ", s)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", _norm(s)).strip()


class PhraseBook:
    def __init__(self, data: dict):
        self.data = data
        self.by_id = {int(e["id"]): e for e in data["sentences"]}
        raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        self.crc32 = zlib.crc32(raw) & 0xFFFFFFFF
        self.key_map: dict[str, int] = {}
        for e in data["sentences"]:
            sid = int(e["id"])
            for k in e.get("keys", []):
                self.key_map[norm(k)] = sid
            self.key_map[norm(e["sentence"])] = sid
            self.key_map[norm(e.get("kind", ""))] = sid

    @classmethod
    def load(cls, path: Path | None = None) -> "PhraseBook":
        return cls(json.loads((path or HERE / "library.json").read_text()))

    def width(self) -> int:
        n = max(self.by_id) if self.by_id else 0
        return 1 if n <= 255 else 2 if n <= 65535 else 4

    def match(self, text: str) -> dict | None:
        t = norm(text)
        if t in self.key_map:
            return self.by_id[self.key_map[t]]
        hits = [k for k in self.key_map if k and k in t]
        if hits:
            hits.sort(key=len, reverse=True)
            return self.by_id[self.key_map[hits[0]]]
        return None

    def slots_from(self, text: str) -> dict:
        slots: dict = {}
        pct = re.search(r"(\d+)\s*(%|percent)", text, re.I)
        if pct:
            slots["pct"] = int(pct.group(1))
        nums = re.findall(r"\b(\d{1,4})\b", text)
        for n in nums:
            v = int(n)
            if slots.get("pct") == v:
                continue
            slots["n"] = v
            break
        return slots

    def fill(self, tmpl: str, slots: dict) -> str:
        def repl(m: re.Match[str]) -> str:
            k = m.group(1)
            if k in slots:
                return str(slots[k])
            return "0" if k in {"pct", "n"} else "—"

        return re.sub(r"\{(\w+)\}", repl, tmpl)


def encode(text: str, book: PhraseBook | None = None) -> dict:
    book = book or PhraseBook.load()
    entry = book.match(text)
    if not entry:
        raise ValueError("no aligned phrase in this book")
    sid = int(entry["id"])
    slots = book.slots_from(text)
    w = book.width()
    mask = 0
    extra = b""
    if "pct" in entry.get("slots", []) and "pct" in slots:
        mask |= 1
        extra += bytes([max(0, min(100, int(slots["pct"])))])
    if "n" in entry.get("slots", []) and "n" in slots:
        mask |= 2
        extra += struct.pack(">H", max(0, min(65535, int(slots["n"]))))
    frame = MAGIC + bytes([w]) + struct.pack(">I", book.crc32) + sid.to_bytes(w, "big") + bytes([mask]) + extra
    sentence = book.fill(entry["sentence"], slots)
    return {
        "id": sid,
        "kind": entry.get("kind"),
        "hex": frame.hex(),
        "frame_bytes": len(frame),
        "utf8_bytes": len(sentence.encode()),
        "frame_vs_utf8_pct": round(100 * len(frame) / max(1, len(sentence.encode())), 2),
        "sentence": sentence,
        "library_crc32": f"{book.crc32:08x}",
        "slots": slots,
        "surfaces": len(entry.get("keys", [])),
    }


def decode(hexstr: str, book: PhraseBook | None = None) -> dict:
    book = book or PhraseBook.load()
    data = bytes.fromhex(re.sub(r"[^0-9a-f]", "", hexstr.lower()))
    if data[:4] != MAGIC:
        raise ValueError("not LEX1")
    w = data[4]
    crc = struct.unpack(">I", data[5:9])[0]
    if crc != book.crc32:
        raise ValueError("library hash mismatch")
    sid = int.from_bytes(data[9 : 9 + w], "big")
    mask = data[9 + w]
    i = 10 + w
    slots: dict = {}
    if mask & 1:
        slots["pct"] = data[i]
        i += 1
    if mask & 2:
        slots["n"] = struct.unpack(">H", data[i : i + 2])[0]
    entry = book.by_id.get(sid)
    if not entry:
        raise ValueError(f"unknown id {sid}")
    sentence = book.fill(entry["sentence"], slots)
    return {
        "id": sid,
        "kind": entry.get("kind"),
        "hex": data.hex(),
        "frame_bytes": len(data),
        "sentence": sentence,
        "slots": slots,
        "library_crc32": f"{book.crc32:08x}",
    }


def stats(book: PhraseBook | None = None) -> dict:
    book = book or PhraseBook.load()
    n = len(book.by_id)
    keys = sum(len(e.get("keys", [])) for e in book.data["sentences"])
    return {
        "name": book.data.get("name"),
        "version": book.data.get("version"),
        "meanings": n,
        "surfaces": keys,
        "width": book.width(),
        "library_crc32": f"{book.crc32:08x}",
        "note": "wire carries id; receiver expands from this book",
    }


if __name__ == "__main__":
    import sys

    book = PhraseBook.load()
    print(json.dumps(stats(book), indent=2))
    samples = [
        "how's it going",
        "whats up",
        "sitrep 94 percent node 7",
        "copy that",
        "stand by 10",
        "good to go 100%",
    ]
    if len(sys.argv) > 1:
        samples = [" ".join(sys.argv[1:])]
    for s in samples:
        enc = encode(s, book)
        dec = decode(enc["hex"], book)
        print(s, "->", enc["id"], enc["kind"], enc["hex"], "|", dec["sentence"])
