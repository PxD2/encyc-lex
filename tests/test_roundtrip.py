#!/usr/bin/env python3
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "phrases"))
sys.path.insert(0, str(ROOT / "warble"))
from codec import PhraseBook, encode, decode
import wrbl

def test_phrase():
    b = PhraseBook.load()
    for s in ["how's it going", "copy that", "sitrep 94 percent node 7"]:
        e = encode(s, b)
        d = decode(e["hex"], b)
        assert d["id"] == e["id"], s
    e = encode("sitrep 94 percent node 7", b)
    assert e["slots"]["pct"] == 94 and e["slots"]["n"] == 7

def test_encyc_shards():
    rows = []
    for p in sorted((ROOT / "shards").glob("part-*.json")):
        rows.extend(json.loads(p.read_text())["sentences"])
    assert [r["id"] for r in rows] == list(range(1, 201))

def test_warble():
    book = wrbl.load_book("phrase")
    recs = [{"id": 1, "slots": {"pct": 94, "n": 7}}, {"id": 2, "slots": {}}]
    p = wrbl.pack(recs, book)
    u = wrbl.unpack(p["hex"], book)
    assert u["hex"] == p["hex"]
    assert "94 percent" in u["expanded"]
    wav = wrbl.warble_wav(bytes.fromhex(p["hex"]), ROOT / "warble" / "test.wav")
    heard = wrbl.hear_wav(wav)
    assert heard.hex() == p["hex"], (heard.hex(), p["hex"])
    book2 = wrbl.load_book("encyc")
    p2 = wrbl.pack([{"id": 200, "slots": {}}], book2)
    assert "galaxy" in p2["expanded"].lower()

if __name__ == "__main__":
    test_phrase(); test_encyc_shards(); test_warble()
    print("ok")
