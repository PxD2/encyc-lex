#!/usr/bin/env python3
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
rows = []
for p in sorted((HERE / 'shards').glob('part-*.json')):
    rows.extend(json.loads(p.read_text())['sentences'])
rows.sort(key=lambda r: int(r['id']))
book = {'name': 'pxd2-encyc-seed', 'version': 2, 'sentences': rows}
(HERE / 'library.min.json').write_text(json.dumps(book, sort_keys=True, separators=(',', ':')) + '\n')
print(len(rows))
