"""Opening old (or hand-made) packs: whatever a pack is missing that the Studio and the game need is put in, from The Quest, and what it says
about itself is made to agree with its folders. Run on a copy in Custom Maps before it is opened; it says what it did and changes nothing
when there is nothing to mend. No windows here."""
from __future__ import annotations

import os
import re
import shutil

from core.project import COMMON_SCRIPT, LEVEL_SCRIPT, TABLES, TEXTS, Grid
from engine import packio
from engine.pack import DEFAULT_PACK


def _level_folders(root):
    d = os.path.join(root, 'levels')
    if not os.path.isdir(d):
        return []
    return sorted(int(f) for f in os.listdir(d) if f.isdigit() and os.path.isdir(os.path.join(d, f)))


def upgrade(root: str) -> list:
    """Mend the pack at `root`; the list of what was done, in words."""
    notes = []
    for f in list(TABLES.values()) + ['tiles.json']:
        if not os.path.isfile(os.path.join(root, f)):
            shutil.copy(os.path.join(DEFAULT_PACK, f), os.path.join(root, f))
            notes.append(f'{f[:-5].capitalize()} were missing, so The Quest\'s were put in ({f}).')
    os.makedirs(os.path.join(root, 'text'), exist_ok=True)
    for key, f in TEXTS.items():
        p = os.path.join(root, 'text', f)
        if not os.path.isfile(p):
            default = os.path.join(DEFAULT_PACK, 'text', f)
            if key == 'questions' and os.path.isfile(default):
                shutil.copy(default, p)
            else:
                packio.write_text(p, '')
            notes.append(f'text/{f} was missing and was made.')
    for folder in ('fonts',):
        if not os.path.isdir(os.path.join(root, folder)) and os.path.isdir(os.path.join(DEFAULT_PACK, folder)):
            shutil.copytree(os.path.join(DEFAULT_PACK, folder), os.path.join(root, folder))
            notes.append(f'The {folder} folder was missing and was copied from The Quest.')
    os.makedirs(os.path.join(root, 'levels'), exist_ok=True)
    if not os.path.isfile(os.path.join(root, 'levels', 'common.qs')):
        packio.write_text(os.path.join(root, 'levels', 'common.qs'), COMMON_SCRIPT)
        notes.append('levels/common.qs was missing and was made.')
    qpath = os.path.join(root, 'quest.json')
    if os.path.isfile(qpath):
        quest = packio.read_json(qpath)
    else:
        quest = packio.read_json(os.path.join(DEFAULT_PACK, 'quest.json'))
        quest.update({'title': os.path.basename(root), 'levels': 0})
        notes.append('quest.json was missing and was made.')
    folders = [n for n in _level_folders(root) if os.path.isfile(os.path.join(root, 'levels', str(n), 'map.txt'))]
    count = 0
    while count + 1 in folders:
        count += 1
    changed = False
    if count and quest.get('levels') != count:
        notes.append(f'It said {quest.get("levels")} levels but has {count}, so it now says {count}.')
        quest['levels'] = count
        changed = True
    if count == 0:
        quest['levels'] = 1
        os.makedirs(os.path.join(root, 'levels', '1'), exist_ok=True)
        packio.write_text(os.path.join(root, 'levels', '1', 'map.txt'), packio.map_text(Grid().rows()))
        notes.append('It had no levels, so one empty level was made.')
        changed = True
    for k, v in (('first_level', 1), ('title', os.path.basename(root)), ('format', 1), ('engine', 'deluxe')):
        if k not in quest:
            quest[k] = v
            changed = True
            if k in ('first_level', 'title'):
                notes.append(f'quest.json had no "{k}": set to {v!r}.')
    for n in range(1, quest['levels'] + 1):
        d = os.path.join(root, 'levels', str(n))
        os.makedirs(d, exist_ok=True)
        if not os.path.isfile(os.path.join(d, 'map.txt')):
            packio.write_text(os.path.join(d, 'map.txt'), packio.map_text(Grid().rows()))
            notes.append(f'Level {n} had no map: an empty one was made.')
        if not os.path.isfile(os.path.join(d, 'script.qs')):
            packio.write_text(os.path.join(d, 'script.qs'), LEVEL_SCRIPT.format(n=n))
            notes.append(f'Level {n} had no script: the plain one was made.')
    if changed or notes:
        packio.write_json(qpath, quest)
    return notes


def import_pack(source: str, folder: str, name: str | None = None) -> tuple[str, list]:
    """Copy a pack folder, or unpack a zip of one, into `folder` (Custom Maps) under a free name and mend the copy; (its folder, what was
    mended). The original is never changed."""
    import tempfile
    import zipfile
    from core import custom
    base = name or re.sub(r'\.zip$', '', os.path.basename(source.rstrip('/\\')), flags=re.I) or 'Imported'
    base = re.sub(r'[^A-Za-z0-9 _.\-]', '', base).strip()[:36] or 'Imported'
    final, n = base, 2
    while custom.valid_name(final, folder) is not None and n < 100:
        final = f'{base} {n}'
        n += 1
    dest = os.path.join(folder, final)
    os.makedirs(folder, exist_ok=True)
    if os.path.isdir(source):
        shutil.copytree(source, dest)
    else:
        with tempfile.TemporaryDirectory() as t, zipfile.ZipFile(source) as z:
            z.extractall(t)
            top = t
            for base_dir, dirs, files in os.walk(t):                 # the folder that holds quest.json, or the data files
                if 'quest.json' in files or 'creatures.json' in files or 'levels' in dirs:
                    top = base_dir
                    break
            shutil.copytree(top, dest)
    notes = upgrade(dest)
    return dest, notes
