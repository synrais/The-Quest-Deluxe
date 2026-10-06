"""editor/pack_edits.py (the zip behind "Send my edits..."): the zip of what was added in the editor.

    python tests/test_pack_zip.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'TheQuestDeluxe-Studio'))
from core import pack_edits as pz  # noqa: E402

PACKS = 'TheQuestDeluxe-Studio/packs'


def png(w: int, h: int) -> bytes:
    """A blank PNG of that size, made by hand (no picture library needed)."""
    import struct
    import zlib

    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))
    raw = b''.join(b'\x00' + b'\x00\x00\x00' * w for _ in range(h))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + \
        chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def fresh_copy() -> str:
    """A main folder with just the packs, as a player has them."""
    tmp = tempfile.mkdtemp()
    shutil.copytree(os.path.join(ROOT, PACKS), os.path.join(tmp, PACKS))
    return tmp


def main():
    # the recorded baseline is the shipped pack as it is (whoever changes the shipped pack runs --baseline)
    shipped = pz.scan(os.path.join(ROOT, PACKS, pz.SHIPPED))
    assert pz.read_baseline() == shipped, 'core/pack_baseline.json is stale: run python TheQuestDeluxe-Studio/core/pack_edits.py --baseline'

    tmp = fresh_copy()
    packs = os.path.join(tmp, PACKS)
    path, report = pz.build(os.path.join(tmp, 'TheQuestDeluxe-Studio'))
    assert path is None and 'nothing to pack' in report, report         # nothing edited: no zip
    # Windows line endings are not an edit
    items = os.path.join(packs, pz.SHIPPED, 'items.json')
    data = open(items, 'rb').read().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    open(items, 'wb').write(data)
    assert pz.build(os.path.join(tmp, 'TheQuestDeluxe-Studio'))[0] is None

    # an edit: a new picture, a changed table, a removed file, and a pack made new
    shutil.copy(os.path.join(packs, pz.SHIPPED, 'sprites', 'items', '1101.png'),
                os.path.join(packs, pz.SHIPPED, 'sprites', 'items', '2500.png'))
    with open(items, 'a', encoding='utf-8') as fh:
        fh.write('\n')
    text = open(items, encoding='utf-8').read().replace('"Ladder"', '"Wooden Ladder"')
    open(items, 'w', encoding='utf-8', newline='').write(text)
    os.remove(os.path.join(packs, pz.SHIPPED, 'sprites', 'items', '1105.png'))
    shutil.copytree(os.path.join(packs, pz.SHIPPED), os.path.join(packs, 'mypack'))
    os.makedirs(os.path.join(packs, pz.SHIPPED, '__pycache__'))
    open(os.path.join(packs, pz.SHIPPED, '__pycache__', 'x.pyc'), 'wb').write(b'0')

    path, report = pz.build(os.path.join(tmp, 'TheQuestDeluxe-Studio'), when=1760000000)
    assert path and os.path.dirname(path) == tmp and os.path.basename(path).startswith('QuestEdits_2025-10-09_'), path
    assert path.endswith('.zip')
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        said = z.read('WHAT_CHANGED.txt').decode()
    assert f'TheQuestDeluxe-Studio/packs/{pz.SHIPPED}/sprites/items/2500.png' in names           # the new picture
    assert f'TheQuestDeluxe-Studio/packs/{pz.SHIPPED}/items.json' in names                         # the changed table
    assert f'TheQuestDeluxe-Studio/packs/{pz.SHIPPED}/sprites/items/1101.png' not in names         # shipped, untouched: not sent
    assert not any('__pycache__' in n or n.endswith('.pyc') for n in names)
    assert f'TheQuestDeluxe-Studio/packs/mypack/quest.json' in names and f'TheQuestDeluxe-Studio/packs/mypack/items.json' in names
    assert 'new: sprites/items/2500.png' in said and 'changed: items.json' in said and 'removed: sprites/items/1105.png' in said
    assert 'packs/mypack: a pack of its own' in said
    # the report says what is in the tables and the pictures
    import json
    data = json.load(open(items, encoding='utf-8'))
    data['items'].append({'id': 2600, 'name': 'Test Mushroom', 'type': 'treasure'})
    json.dump(data, open(items, 'w', encoding='utf-8'))
    tiles = os.path.join(packs, pz.SHIPPED, 'tiles.json')
    t = json.load(open(tiles, encoding='utf-8'))
    for w in t['walls']:
        if w['id'] == 2:
            w['freezes_to'] = -7
    json.dump(t, open(tiles, 'w', encoding='utf-8'))
    os.makedirs(os.path.join(packs, pz.SHIPPED, 'sprites', 'items', 'new items'))
    open(os.path.join(packs, pz.SHIPPED, 'sprites', 'items', 'new items', '9.png'), 'wb').write(png(40, 40))
    open(os.path.join(packs, pz.SHIPPED, 'sprites', 'creatures', '777.png'), 'wb').write(png(80, 80))
    open(os.path.join(packs, pz.SHIPPED, 'sprites', 'creatures', 'big.png'), 'wb').write(png(40, 40))
    path3, report3 = pz.build(os.path.join(tmp, 'TheQuestDeluxe-Studio'), when=1760000120, note='I could not freeze the water.')
    assert "NEW items 2600 'Test Mushroom'" in report3 and "CHANGED walls 2 'Water': freezes_to: null -> -7" in report3
    assert 'sprites/creatures/777.png: 80 x 80   WARNING: 80 x 80, not 40 x 40: it is scaled' in report3
    assert 'sprites/items/new items/9.png: 40 x 40   WARNING: not where the editor looks' in report3
    assert 'sprites/creatures/big.png: 40 x 40   WARNING: the name is not a number' in report3
    assert 'NOTE FROM WHOEVER MADE THIS:\nI could not freeze the water.' in report3
    with zipfile.ZipFile(path3) as z:
        assert z.read('NOTES.txt').decode().strip() == 'I could not freeze the water.'
    # a game folder without the recorded baseline says so, and sends all of the pack
    nobase, said = pz.build(os.path.join(tmp, 'TheQuestDeluxe-Studio'), when=1760000180, baseline=os.path.join(tmp, 'missing.json'))
    assert 'pack_baseline.json is missing' in said and nobase
    # what was written in the editor's Wishes window leads the report, and goes in the zip
    open(os.path.join(packs, pz.SHIPPED, 'WISHES.txt'), 'w', encoding='utf-8').write(
        '# Things I wish\n- 2026-10-02: a spell that makes it rain\n')
    path4, report4 = pz.build(os.path.join(tmp, 'TheQuestDeluxe-Studio'), when=1760000240)
    assert 'WISHES (packs/TheQuest/WISHES.txt):\n- 2026-10-02: a spell that makes it rain' in report4
    assert '# Things I wish' not in report4
    with zipfile.ZipFile(path4) as z:
        assert f'TheQuestDeluxe-Studio/packs/{pz.SHIPPED}/WISHES.txt' in z.namelist()
    # --all: everything
    path_all, _ = pz.build(os.path.join(tmp, 'TheQuestDeluxe-Studio'), include_all=True, when=1760000060)
    with zipfile.ZipFile(path_all) as z:
        assert f'TheQuestDeluxe-Studio/packs/{pz.SHIPPED}/sprites/items/1101.png' in z.namelist()
    # unzipped over a copy of the repository, the files land where they belong
    other = fresh_copy()
    with zipfile.ZipFile(path) as z:
        z.extractall(other)
    assert os.path.exists(os.path.join(other, PACKS, 'mypack', 'quest.json'))
    assert os.path.exists(os.path.join(other, PACKS, pz.SHIPPED, 'sprites', 'items', '2500.png'))
    # a wrong folder says so
    assert pz.build(os.path.join(tempfile.mkdtemp(), 'TheQuestDeluxe-Studio'))[0] is None
    print('Make Edits Zip: only what is new or changed goes in the zip, new packs whole, dated, unzips in place: ok')


if __name__ == '__main__':
    main()
