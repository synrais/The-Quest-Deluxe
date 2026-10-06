"""What the original can hold: a hero from a pack may carry things the DOS game has never heard of (a new weapon, a spell past the twentieth,
a fifth class). The original's save has no room for them, so they are left out of what it is given, and said.

Pure data: no windows, no engine."""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL_PACK = os.path.join(ROOT, 'packs', 'TheQuest')


def original_ids() -> dict:
    """The numbers the original's own data has: {'items': set, 'spells': set, 'classes': set}."""
    out = {}
    for kind, key in (('items', 'items'), ('spells', 'spells'), ('classes', 'classes')):
        with open(os.path.join(ORIGINAL_PACK, f'{kind}.json'), encoding='utf-8') as fh:
            out[kind] = {r['id'] for r in json.load(fh)[key]}
    return out


def strip_unknown(save, ids: dict | None = None) -> list:
    """Take from a savefile.SaveData what the original does not have; the list of what was taken: [(what, number, where)]."""
    ids = ids or original_ids()
    gone = []
    for cell, item in list(save.bag.items()):
        if item and item not in ids['items']:
            save.bag[cell] = 0
            gone.append(('item', item, 'bag'))
    for cell, sp in list(save.book.items()):
        if sp and sp not in ids['spells']:
            save.book[cell] = 0
            gone.append(('spell', sp, 'spell book'))
    for i in range(1, len(save.spells)):
        if save.spells[i] and (save.spells[i] not in ids['spells'] and save.spells[i] not in (0, 1)):
            gone.append(('spell', save.spells[i], 'known spells'))
            save.spells[i] = 0
    if save.extra:
        for k in ('spells', 'book', 'more', 'levels'):
            if save.extra.get(k):
                gone.append(('deluxe extras', 0, k))
        save.extra = {}
    if save.hero.get('type') not in ids['classes']:
        gone.append(('class', save.hero.get('type'), 'hero'))
        save.hero['type'] = 1
    return gone


def describe(gone: list) -> str:
    if not gone:
        return ''
    bits = {}
    for what, n, where in gone:
        bits.setdefault(what, []).append(n if n else where)
    return 'The original does not have: ' + '; '.join(f'{k} {", ".join(str(v) for v in vs)}' for k, vs in bits.items()) + ' (left out of both)'
